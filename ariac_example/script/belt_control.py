#!/usr/bin/env python3

import rospy
import tf2_ros
import moveit_commander as mc
import math
import yaml
from yaml.loader import SafeLoader

import tf2_listener
import json

import geometry_msgs.msg
from tf.transformations import euler_from_quaternion
from nist_gear.msg import VacuumGripperState, Proximity, LogicalCameraImage
from nist_gear.srv import VacuumGripperControl, ConveyorBeltControl
from std_srvs.srv import Trigger
from std_msgs.msg import String

# from scipy.spatial import distance

import sys
import os

# for multithreading
import threading
import queue

# Battery z-value grab heights on conveyor
BATTERY_HEIGHT = 0.03
SENSOR_HEIGHT = 0.048
REGULATOR_HEIGHT = 0.05

def print_robot_list(robotObjects):
    for i in robotObjects:
        for j in i:
            print("id = %d, type = %s, name = %s" % (j.id, j.type, j.name))

def competition_state():
    data = rospy.wait_for_message('/ariac/competition_state', String)
    return data

def start_competition():
    """ Start the competition through ROS service call """

    rospy.wait_for_service('/ariac/start_competition')
    rospy.ServiceProxy('/ariac/start_competition', Trigger)()

def get_logical_camera_conveyor_data():
    try:
        data = rospy.wait_for_message('/ariac/logical_camera_conveyor', LogicalCameraImage)
        print("data: ", data)
        return data
    except rospy.ROSException:
        print("rospy message timeout")
        return LogicalCameraImage()


def control_conveyor(power):
    if power < 0 or power > 100:
        print("Power must be in range (0,100)")
        return

    rospy.wait_for_service('/ariac/conveyor/control')
    conveyor_rosservice = rospy.ServiceProxy('/ariac/conveyor/control', ConveyorBeltControl)
    try:
        conveyor_rosservice(power)
    except rospy.ServiceException as exc:
        print("Service did not process request: " + str(exc))

# JSON parser function
# Input: JSON file
# Output: robotObjects - 2D array of RobotObjects (ordered Kitting, Gantry, AGV, Conveyor)
def parse_json(file):
    f = open(file)
    data = json.load(f)

    robotObjects = [[]]
    ur10_upper_arm_len = 0.612
    ur10_forearm_len = 0.5723
    id_count = 0
    for i in data['robots']:
        if i['type'] == 'conveyor':
            robotObjects[0].append(ConveyorRobot(i['name'], i['pose'], i['orient'], i['orient_range'], id_count))
            id_count += 1
        else:
            raise Exception("Error: Robot type ", i['type'], " does not exist")

    global num_robots
    num_robots = id_count

    return robotObjects

def conveyor_loop(q, t):
    conveyorPlan = Conveyor_Sensor_module()
    lastState = 0
    while conveyorPlan.main_body(q, t) is False:
        curState = conveyorPlan.conveyor_state
        if curState != lastState:
            print("conveyor state:", conveyorPlan.conveyor_state)
        # else:
            # print("conveyor state still 0:", conveyorPlan.conveyor_state)
        lastState = curState
        rospy.sleep(0.05)

class Conveyor_Sensor_module():
    def __init__(self):
        self.conveyor_state = 0
        self.target = ""

    def main_body(self, q, t):
        # Conveyor State 0: Pre-competition (stopped)
        if self.conveyor_state == 0:
            print("conveyor state 0")
            if competition_state().data == "init":
                print("start competition is called")
                start_competition()  # conveyor begins to move
            # start_competition()
            self.conveyor_state = 1
            return False



        # Conveyor State 1: Waiting for a needed item (moving)
        if self.conveyor_state == 1:
            print("entering state 1")
            detected = False
            models_detected = get_logical_camera_conveyor_data().models  # not getting the message?!
            print(len(models_detected))

            # if len(models_detected) == 0:
            #     print("no model detected")
            #     return False

            for m in models_detected:
                print("in for loop")
                # if m.type in order and order[m.type] > 0:
                self.target = m.type
                detected = True
                print("model detected")
                break

            if not detected:
                print("not detected")
                return False

            rospy.sleep(0.05)

            control_conveyor(0)
            self.conveyor_state = 2  # conveyor paused
            # self.kitting_state = 2	# kitting arm moves down to grab item
            t.append(self.target)
            return False

        # Conveyor State 2: conveyor paused
        if self.conveyor_state == 2:
            print("in state 2")
            # stay in this state until we get a signal from kitting FSM
            while True:
                msg = q.get()
                # operation finished, exit thread
                if msg == "done":
                    return True
                elif msg == "run":
                    break
                else:
                    rospy.sleep(0.05)

            control_conveyor(100)
            self.conveyor_state = 1
            return False

class Line:
    def __init__(self, pose, orient, orient_range):
        self.orient = orient
        self.orient_range = orient_range
        self.point_2d = self.get_point(pose)

    def get_point(self, x):
        point = []
        for dim in range(3):
            if dim != self.orient:
                point.append(x[dim])
        return point

class ConveyorRobot:
    def __init__(self, name, pose, orient, orient_range, id_count):
        self.type = 'conveyor'
        self.name = name
        self.pose = pose  # center pose [x,y,z]
        self.orient = orient  # 0 = runs along x-direction, 1 = runs along y-direction
        self.orient_range = orient_range
        self.height = 0.90
        # self.dim = dim   # [x length, y length, z height]
        # compute line for this (see intersect_kitting_conveyor for formatting)
        self.shape = Line([pose[0], pose[1], self.height], orient, orient_range)
        self.id = id_count

if __name__ == '__main__':

    global robotObjects
    robotObjects = parse_json(sys.argv[1])  # [conveyor]

    print_robot_list(robotObjects)

    rospy.init_node("node", anonymous=True)

    order = {"assembly_battery_green": 1, "assembly_battery_blue": 0}
    global total_output
    total_output = sum(order.values())  # checks when we are done with operation

    print(total_output)

    q = queue.Queue()  # to send signals between threads
    t = []  # signal telling which item to grab
    global gq  # signal between AGVs and gantrys
    gq = []
    conveyor_thread = threading.Thread(target=conveyor_loop, args=(q, t,))

    conveyor_thread.start()
    conveyor_thread.join()
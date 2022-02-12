#!/usr/bin/env python

import rospy
import tf2_ros
import moveit_commander as mc
import math
import yaml
from yaml.loader import SafeLoader

import tf2_listener

import geometry_msgs.msg
from tf.transformations import euler_from_quaternion
from nist_gear.msg import VacuumGripperState, Proximity, LogicalCameraImage
from nist_gear.srv import VacuumGripperControl, ConveyorBeltControl
from std_srvs.srv import Trigger
from std_msgs.msg import String

import sys
import os

# for multithreading
import threading
import Queue

# Battery z-value grab heights on conveyor
BATTERY_HEIGHT = 0.03
SENSOR_HEIGHT = 0.048
REGULATOR_HEIGHT = 0.05

def start_competition():
    """ Start the competition through ROS service call """

    rospy.wait_for_service('/ariac/start_competition')
    rospy.ServiceProxy('/ariac/start_competition', Trigger)()

def competition_state():
	data = rospy.wait_for_message('/ariac/competition_state', String)
	print(data)
	return data

def get_order():
    """ Get the current order from the /ariac/orders topic"""

    order = rospy.wait_for_message('/ariac/orders', Order)
    return order

def move_agvs(agv, dest):
	rospy.wait_for_service('/ariac/' + agv + '/to_' + dest)
	rospy.ServiceProxy('/ariac/' + agv + '/to_' + dest, Trigger)()

def get_breakbeam_sensor_data():
	data = rospy.wait_for_message('/ariac/breakbeam_conveyor', Proximity)
	return data
def get_breakbeam_flat_sensor_data():
	data = rospy.wait_for_message('/ariac/breakbeam_conveyor_flat', Proximity)
	return data
def get_logical_camera_conveyor_data():
	data = rospy.wait_for_message('/ariac/logical_camera_conveyor', LogicalCameraImage)
	return data

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

def find_alphabeta(x, z):
	r1 = 0.61215	# range of motion of shoulder lift joint
	r2 = 0.57235	# range of motion of elbow joint
	#r1 = 0.573 # length of upper arm link (radius of its range of motion)
	#r2 = 0.400 # length of forearm link

	ab = euclidean_dist(-1.3, 1.1264, x, z) # dist from kitting base joint to desired (x,z) point (a + b in proof)
	beta = law_cosines_gamma(r1, r2, ab)

	a1 = law_cosines_gamma(r1, ab, r2)
	a2 = math.acos((abs(x+1.3))/ab)
	# alpha = alpha' + alpha'' if goal z is above start z
	if z >= 1.1264:
		alpha = a1 + a2
	else:
		alpha = a1 - a2

	alpha = -alpha			# moving shoulder joint up is negative alpha direction
	beta = math.pi - beta	# we want complementary (beta is angle b/t two links, elbow joint is comp of this)
	# the above might need additional changes (e.g. abs val, etc) when trying to grab stuff on other side

	return (alpha, beta)

def euclidean_dist(x1, z1, x2, z2):
	return math.sqrt((x2-x1)**2 + (z2-z1)**2)

def euclidean(a, b):
	if len(a) != len(b):
		assert("Inputs of different dimensions")

	tmp_sum = 0
	for i in range(len(a)):
		tmp_sum += (b[i] - a[i])**2

	return tmp_sum**0.5

def new_euclidean_dist(a, b):
	if type(a) is not tuple or type(b) is not tuple or len(a) != len(b):
		raise Exception('Invalid input for euclidean distance!')
	
	squared_sum = 0
	for i in range(len(a)):
		squared_sum += (abs(b[i]-a[i]))**2

	return squared_sum**0.5

# Input - two ranges (e.g. a = [3,5], b = [4,8])
# Output - boolean
def overlap(a, b):
	# swap if out of order
	if a[0] > b[0]:
		tmp = a
		a = b
		b = tmp

	return a[1] > b[0]

def reachable(a, b):
	# Normal cases: y-coordinate of point is within linear rail range
	if b[1] < a[1] + rail_length and b[1] > a[1] - rail_length:
		return new_euclidean_dist(a[0::2], b[0::2]) <= max_radius
	# Edge cases: y-coordinate of point is outside linear rail range
	else:
		print("edge case!")
		# TODO: check 'hemispheres' outside linear rail range
		return False

# Uses law of cosines to find the angle (in radians) of the side opposite of c
def law_cosines_gamma(a, b, c):
	return math.acos((a**2 + b**2 - c**2)/(2*a*b))

def bounds_checking(x, z):
	return True if euclidean_dist(x-0.1158, z+0.1, -1.3, 1.12725) <= 1.1845 else False

class KittingRobot:
    def __init__(self, pose, orient, orient_range, max_r, id_count):
        self.type = 'kitting'
        self.pose = pose           # center pose - [x,y,z]
        self.orient = orient   # direction in which rail runs: 0=x, 1=y
        self.orient_range = orient_range   # range in its oriented direction (aka rail length)
        self.max_r = max_r
        self.shape = Cylinder(pose, orient, orient_range, max_r)
        self.id = id_count
        id_count += 1
        
    # Returns boolean indicating whether there exists intersection with a Gantry Robot
    def intersect_w_gantry(self, GantryObject):
        pass
    
    def intersect_w_conveyor(self, ConveyorObject):
        # ASSUMPTION FOR NOW: kitting and conveyor lie in same direction
        # check if oriented direction overlaps
        if not overlap(self.orient_range, ConveyorObject.orient_range):
            return false

        # check if other two directions overlap (for now, if line lies inside cylinder -> if point inside circle)
        return euclidean(self.shape.circle_center, ConveyorObject.shape.point_2d) < self.shape.r

    def intersect_w_agv(self, AGVObject):
        # ASSUMPTION: only kitting can intersect with starting point
        # check start point's vertical line intersects with kitting cylinder
        return self.shape.intersect_w_line(AGVObject.start_shape) # TODO: implement intersect_w_line func

class GantryRobot:
	def __init__(self, pose, x_rail_range, y_rail_range, arm_r, id_count):
		self.type = 'gantry'
		self.pose = pose
		self.x_rail_range = x_rail_range   # [x_min, x_max]
		self.y_rail_range = y_rail_range   # [y_min, y_max]
		self.arm_r = arm_r
		self.id = id_count
		id_count += 1

	# TODO
	# ASSUMPTION: since AGV -> gantry for now, gantry can only intersect w one of dest vert. lines
	def intersect_w_agv(self, AGVObject):
		return True
        
class AGVRobot:
	def __init__(self, pose, orient, dst, id_count):
		# ASSUMPTION: z-range hardcoded for now (twice in this function)
		self.type = 'agv'
		self.start_shape = Line(pose, 2, [0.81, 2])   # starting pose's vertical line
		self.orient = orient   # 0=x, 1=y
		self.shape = []   # list of vertical lines
		for i in dst:
			self.shape.append(Line(pose, 2, [0.81,2]))
		self.id = id_count
		id_count += 1
        
class ConveyorRobot:
    def __init__(self, pose, orient, orient_range, dim, id_count):
        self.type = 'conveyor'
        self.pose = pose   # center pose [x,y,z]
        self.orient = orient   # 0 = runs along x-direction, 1 = runs along y-direction
        self.orient_range = orient_range
        self.dim = dim   # [x length, y length, z height]
        # compute line for this (see intersect_kitting_conveyor for formatting)
        self.shape = Line([pose[0],pose[1],dim[2]], orient, orient_range)
        self.id = id_count
        id_count += 1

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

class Cylinder:
	def __init__(self, pose, orient, orient_range, max_r):
		self.orient = orient
		self.orient_range = orient_range
		self.circle_center = self.get_point(pose)
		self.r = max_r

	def get_point(self, x):
		point = []
		for dim in range(3):
			if dim != self.orient:
				point.append(x[dim])
		return point

	# TODO: incomplete. Possibly simply to boxes
	def intersect_w_line(self, line):
		# if both are oriented the same way, check:
		# 1) line's point is inside cylinder's circle
		# 2) if line and cylinder's ranges intersect
		if self.orient == line.orient:
			return True
		# if not oriented same way, 
		else:
			return True

class Graph:
	# edges - connectivity list (2D array) of robotObjects -> [[a,b,c],[],[a,d]] -> robot_id=0 is connected to robotObjects a,b,c
	def __init__(self, edges):
		self.num_v = len(edges)   # number of vertices, ordered 0,1,2,...,v-1
		self.e = edges
	
	# Runs DFS starting on specified vertex/robotObject (rep. by robot_id)
	# Input: start_v - robot_id of robotObject we want to run DFS starting at
	# ASSUMPTION: conveyor -> kitting -> AGV -> conveyor
	def dfs(self, start_v):
		seen = set()
		seen.add(start_v)
		self.dfs_helper(start_v, self.e, seen)
		return seen
	
	# Input: cur - robot_id of robotObject we are currently at in DFS
	# Output: none
	# Side effects: updates seen set
	def dfs_helper(self, cur, edge_list, seen):
		for r in edge_list[cur]:
			if r not in seen:
				seen.add(r)
				self.dfs_helper(r, edge_list, seen)
		return

# Input: robotObjects - a 2D list of robot objects (ordered KittingObject, GantryObject, AGVObject, ConveyorObject)
# ASSUMPTION: for now, assuming conveyor -> kitting -> AGV -> gantry
def build_graph(robotObjects):
	e = []   # index corresponds to robot_id
	for i in range(num_robots):
		e.append([])

    # detect conveyor -> kitting edges
	for c_obj in robotObjects[3]:
		tmp_e = []
		for k_obj in robotObjects[0]:
			if k_obj.intersect_w_conveyor(c_obj):
				tmp_e.append(k_obj.id)
		e[c_obj.id] = tmp_e

	# detect kitting -> AGV edges
	for k_obj in robotObjects[0]:
		tmp_e = []
		for agv_obj in robotObjects[2]:
			if k_obj.intersect_w_agv(agv_obj):
				tmp_e.append(agv_obj.id)
		e[k_obj.id] = tmp_e

	# detect AGV -> gantry edges
	for agv_obj in robotObjects[2]:
		tmp_e = []
		for g_obj in robotObjects[1]:
			if g_obj.intersect_w_agv(agv_obj):
				tmp_e.append(g_obj.id)
		e[agv_obj.id] = tmp_e

	return Graph(e)

# Input : robotObjects - a 2D list of robot objects (ordered KittingObject, GantryObject, AGVObject, ConveyorObject)
def connectivity(robotObjects):
	g = build_graph(robotObjects)
	connected = set()
	for c_obj in robotObjects[3]:
		s = g.dfs(c_obj.id)

		# Merge sets
		for i in s:
			connected.add(i)

	return len(connected) == num_robots


def pick_place(moveit_runner_kitting, moveit_runner_gantry, kitting_gm, gantry_gm):
	while True:
		src = input("\nEnter pick (source) pose in form (x, y, z): ")
		if len(src) == 3:
			break
		print("Input formatted incorrectly. Please try again")
	
	while True:
		dst = input("\nEnter place (dest) pose in form (x, y, z): ")
		if len(dst) == 3:
			break
		print("Input formatted incorrectly. Please try again")

	# Check if pick-and-place operation is possible under the given constraints
	if not reachable(kitting_base, src):
		print("Pick (source) location is out of kitting robot's range.")
		exit()
	
	if not reachable(kitting_base, dst):
		print("Place (dest) location is out of kitting robot's range.")
		exit()

    # Boot up simulation (Gazebo) with the auto-generated controller
	moveit_runner_kitting.goto_pose(src[0], src[1], src[2])
	kitting_gm.activate_gripper()
	moveit_runner_kitting.goto_pose(dst[0], dst[1], dst[2])
	kitting_gm.deactivate_gripper()


class MoveitRunner():
	def __init__(self, group_names, node_name='move_kitting',
				 ns='', robot_description='robot_description'):

		mc.roscpp_initialize(sys.argv)
		rospy.init_node('move_kitting', anonymous=True)

		self.robot = mc.RobotCommander(ns+'/'+robot_description, ns)
		self.scene = mc.PlanningSceneInterface(ns)
		self.groups = {}
		for group_name in group_names:
			group = mc.MoveGroupCommander(group_name, 
					   robot_description=ns+'/'+robot_description, 
					   ns=ns)
			group.set_goal_tolerance(0.0001)	# toggle this on and off
			self.groups[group_name] = group

	def goto_pose(self, x, y, z):

		# TODO: incorporate roll pitch yaw in user input
		orientation_k = kitting_arm.get_current_pose().pose.orientation
		(roll, pitch, yaw) = euler_from_quaternion([orientation_k.x, orientation_k.y, orientation_k.z, orientation_k.w]) 

		# Bounds checking
		if y > 4.8 or y < -4.8:
			return False
		if not bounds_checking(x, z):
			return False

		conveyor_side = True if x >= -1.3 else False

		# Finding alpha (shoulder lift angle) and beta (elbow joint angle)
		if conveyor_side:
			alpha, beta = find_alphabeta(x-0.1158, z+0.1)	# adjust these values to account for wrist lengths
		else:
			alpha, beta = find_alphabeta(x+0.1154, z+0.1)

		cur_joint_pose = moveit_runner_kitting.groups['kitting_arm'].get_current_joint_values()

		# linear arm actuator
		if not conveyor_side:
			cur_joint_pose[0] = y + 0.1616191
		else:
			cur_joint_pose[0] = y - 0.1616191

		# shoulder pan joint
		if x < -1.3:
			cur_joint_pose[1] = 3.14
		else:
			cur_joint_pose[1] = 0

		# shoudler lift (alpha) and elbow (beta)
		cur_joint_pose[2] = alpha
		cur_joint_pose[3] = beta

		# to get flat ee: w1 = - shoulder lift - elbow - pi/2
		cur_joint_pose[4] = -1*cur_joint_pose[2] - cur_joint_pose[3] - math.pi/2

		# wrist 2 (always -pi/2 for now, until we incorporate roll, pitch, yaw)
		cur_joint_pose[5] = -math.pi/2

		# wrist 3
		cur_joint_pose[6] = 0

		print(cur_joint_pose)

		self.groups['kitting_arm'].go(cur_joint_pose, wait=True)
		self.groups['kitting_arm'].stop()		

		# TODO: eventually want to check with tf frames if move was successful or not
		return x, y, z

class GripperManager():
	def __init__(self, ns):
		self.ns = ns
	
	def activate_gripper(self):
		rospy.wait_for_service(self.ns + 'control')
		rospy.ServiceProxy(self.ns + 'control', VacuumGripperControl)(True)

	def deactivate_gripper(self):
		rospy.wait_for_service(self.ns + 'control')
		rospy.ServiceProxy(self.ns + 'control', VacuumGripperControl)(False)

	def is_object_attached(self):
		status = rospy.wait_for_message(self.ns + 'state', VacuumGripperState)
		return status.attached


if __name__ == '__main__':

	kitting_group_names = ['kitting_arm']
	moveit_runner_kitting = MoveitRunner(kitting_group_names, ns='/ariac/kitting')
	kitting_arm = moveit_runner_kitting.groups['kitting_arm']
	kitting_arm.set_end_effector_link("vacuum_gripper_link")
	kitting_gm = GripperManager(ns='/ariac/kitting/arm/gripper/')

	gantry_group_names = ['gantry_full', 'gantry_arm', 'gantry_torso']
	moveit_runner_gantry = MoveitRunner(gantry_group_names, ns='/ariac/gantry')
	gantry_gm = GripperManager(ns='/ariac/gantry/arm/gripper/')

	# Read in data from JSON file (replace with actual code later)
	kitting_world_x = -1.3  # eventually, will want to set kitting.urdf.xacro file with this info
	kitting_world_y = 0
	kitting_world_z = 0.9

	linear_actuator_height = 0.1	# from linear_arm_actuator.urdf.xacro
	shoulder_height = 0.1273

	global kitting_base
	kitting_base = (kitting_world_x, kitting_world_y, kitting_world_z + linear_actuator_height + shoulder_height)
	# kitting_base_x = kitting_world_x
	# kitting_base_y = kitting_world_y
	# kitting_base_z = kitting_world_z + linear_actuator_height + shoulder_height

	# eventually, want to set these values in linear_arm_actuator.urdf
	base_len = 0.2
	actuator_len = 10

	# length kitting robot can slide in one direction from origin-y
	global rail_length
	rail_length = actuator_len/2 - base_len

	# Retrieve robot arm parameters -- assuming this isn't part of user input
	upper_arm_length = 0.612
	forearm_length = 0.5723
	global max_radius
	max_radius = upper_arm_length + forearm_length

	k = KittingRobot([-1.3,0,1.127],1,[-4.8,4.8],1.1843,0)
	a = AGVRobot([-2.266, 4.675, 0],0,[[-2.266, 4.675, 0],[-5.6, 4.675, 0], [-10.590, 4.675, 0]],1)
	c = ConveyorRobot([-0.57,0,0],1,[-4.8,4.8],[0.5,10,0.9],2)
	robotObjects = [[k],[],[a],[c]]

	global num_robots
	num_robots = 0
	for i in robotObjects:
		num_robots += len(i)

	# Level 2 Consistency Check - connectivity (for now, assuming conveyor -> kitting -> AGV -> gantry)
	print('connected? ', connectivity(robotObjects))

	# Pick-and-place operation
	# make call to function
    

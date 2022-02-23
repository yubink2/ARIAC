#!/usr/bin/env python
# Copyright 2017 Open Source Robotics Foundation, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import geometry_msgs.msg
import rospy
import tf2_ros
import tf2_geometry_msgs  # import support for transforming geometry_msgs stamped msgs

def get_transformed_pose(source_frame, target_frame):
    # rospy.init_node('tf2_example') -> don't need this since we already have one in our own file?

    tfBuffer = tf2_ros.Buffer()
    listener = tf2_ros.TransformListener(tfBuffer)

    # The shipping box TF frames are published by logical cameras, or can be published
    # by user-created TF broadcasters.
    # source_frame = 'logical_camera_conveyor_frame'
    # target_frame = 'logical_camera_conveyor_assembly_battery_green_1_frame'
    rate = rospy.Rate(1.0)
    while not rospy.is_shutdown():
        # Ensure that the transform is available.
        try:
            # trans = tfBuffer.lookup_transform('world', frame, rospy.Time(), rospy.Duration(1.0))
            trans = tfBuffer.lookup_transform(source_frame, target_frame, rospy.Time(), rospy.Duration(1.0))
        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException) as e:
            print(e)
            break

        # Transform the pose from the specified frame to the world frame.
        local_pose = geometry_msgs.msg.PoseStamped()
        # local_pose.header.frame_id = frame
        local_pose.header.frame_id = target_frame
        # local_pose.pose.position.x = 0.15
        # local_pose.pose.position.y = 0.15

        world_pose = tfBuffer.transform(local_pose, 'world')
        return world_pose
        # print(world_pose)
        rate.sleep()

if __name__ == '__main__':
    pass

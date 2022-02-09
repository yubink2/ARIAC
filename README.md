# Wiki | Home

## Difference in theis fork

This is a fork of ARIAC 2021 competition for our Smart Manufacturing research 
in [Reliable Autonomy research Lab](https://mitras.ece.illinois.edu/group.html).

The main differences between this fork and the original competition are the
following:

+ Support ROS Noetic with Gazebo 11 on Ubuntu 20.04 LTS. **TODO** Compilation
  instructions for ROS Noetic with Gazebo 11.
+ Remove dependencies on `ariac-gazebo_ros_pkgs` and use `gazeo_ros_pkgs` for
  ROS Noetic.
  This removes several restrictions enforced by the competition that avoids 
  querying and controlling the internal state of Gazebo.
+ Start simulation environment in developer mode by default.


## Welcome to ARIAC 2021.

<!-- **NOTE**: These pages are in the process of being updated. If you see something that looks like it got missed, please send us an email at ariac@nist.gov -->

![ariac-2021](wiki/figures/ariac2021_environment.jpeg)

- This year, the theme revolves around the pandemic. 
  - Competitors will be tasked to manipulate products used in the assembly of ventilators. 
  - Kitting (or kit building) and assembly are the two tasks involved in ARIAC 2021.

- **NOTE**: The [Updates](wiki/misc/updates.md) section provides a description of the updates that come with each new release of the software.
  
```diff
- NOTE: Always use the master branch to retrieve the latest updates.
```

```diff
- NOTE: Always review the Updates section when new code is pushed.
```
<!---<img src="wiki/figures/ariac2020_3.jpg" alt="alt text" width="600" class="center">-->

## Important Dates

- 22-26 March 2021 - Smoke Test Week before Qualifier Round
- 03-10 May 2021 - Qualifier Round (Files must be submitted by May 10, 9 am EST)
- 31 May-04 June 2021 - Smoke Test before Final Round
- 07-11 June 2021 - Final Round

## [Installation](wiki/tutorials/installation.md)

- Steps to install and run ARIAC.

## [Terminology](wiki/misc/terminology.md)

- This section describes the terminology used in this wiki. If you are new to ARIAC we strongly suggest you visit this page first.
  
## [Updates](wiki/misc/updates.md)

- Check this page for recent updates made to the code.

## [What is new in ARIAC 2021?](wiki/misc/whatisnew.md)

- Summary of the changes made since ARIAC 2020.

## [Documentation](wiki/documentation/documentation.md)

- Specifications of the NIST Agile Robotics for Industrial Automation Competition (ARIAC) and the Gazebo Environment for Agile Robotics (GEAR) software.

## [Tutorials](wiki/tutorials/tutorials.md)

- A set of tutorials to help you get started with the NIST Agile Robotics for Industrial Automation Competition (ARIAC).

## [Qualifiers](wiki/qualifiers/qualifier.md)

- Details of the released qualification tasks for ARIAC.

## [Finals](wiki/finals/finals.md)

- Details of how the ARIAC Finals will run.

## [Bug Reports](wiki/misc/bug_report.md)

- Improving the software and fixing issues.

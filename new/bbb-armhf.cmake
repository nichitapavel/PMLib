# Cross compilling related settings
# Beagle Bone Black
# Debian 8.11 Jessie
set(CMAKE_SYSTEM "Linux-4.4.54-ti-r93")
set(CMAKE_SYSTEM_NAME "Linux")
set(CMAKE_SYSTEM_VERSION "4.4.54-ti-r93")
set(CMAKE_SYSTEM_PROCESSOR "armhf")

set(COMPILER_ROOT_PATH "/opt/gcc-linaro-4.9.4-2017.01-x86_64_arm-linux-gnueabihf/bin/arm-linux-gnueabihf-")
set(CMAKE_C_COMPILER "${COMPILER_ROOT_PATH}gcc")
set(CMAKE_CXX_COMPILER "${COMPILER_ROOT_PATH}g++")

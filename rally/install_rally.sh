#!/bin/bash
# Install and configure rally

if [ -z $1 ]; then
    image="cirros"
else
	image=$1
fi

source rally_venv
source ../openrc
# Gather vars for tempest template
image_name=$(openstack image list | grep $image | awk '{ print $4 }')

# Git rally, place the rendered rally template
[ -d rally_scenarios ] || mkdir -p rally_scenarios

# Insert the image to use
for i in rally-templates/*.yaml; do
	out_file=$(basename $i)
	sed -e s:__IMAGE__:$image_name:g $i > rally_scenarios/$out_file
done

rally db recreate

# Creating environment
rally deployment create --fromenv --name=existing


echo
echo "Finished installing rally"
echo
echo "To run a task run the following command (for example): "
echo "source rally_venv"
echo "rally task start rally_scenarios/boot.yaml"




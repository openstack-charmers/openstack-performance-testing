# Copyright 2014 PerfKitBenchmarker Authors. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Module containing iperf installation and cleanup functions."""

from absl import flags
import posixpath

from perfkitbenchmarker import errors
from perfkitbenchmarker import linux_packages

FLAGS = flags.FLAGS
PACKAGE_NAME = 'iperf'
IPERF_TAR = 'iperf-2.0.13.tar.gz'
IPERF_URL = 'https://sourceforge.net/projects/iperf2/files/iperf-2.0.13.tar.gz'
IPERF_DIR = '%s/iperf-2.0.13' % linux_packages.INSTALL_DIR


def _Install(vm):
  """Installs the iperf package on the VM."""
  vm.Install('build_tools')
  vm.Install('wget')
  if FLAGS.http_proxy:
    #http_proxy = "sed -i '1i export http_proxy=%s' /etc/bash.bashrc"
    http_proxy = "echo 'http_proxy = %s' >> /home/ubuntu/.wgetrc"
    vm.RemoteCommand(http_proxy % FLAGS.http_proxy)
  if FLAGS.https_proxy:
    https_proxy = "echo 'https_proxy = %s' >> /home/ubuntu/.wgetrc"
    #https_proxy = "sed -i '1i export https_proxy=%s' /etc/bash.bashrc"
    vm.RemoteCommand(https_proxy % FLAGS.https_proxy)

  vm.RemoteCommand('wget -O %s/%s %s' %
                   (linux_packages.INSTALL_DIR, IPERF_TAR, IPERF_URL))

  vm.RemoteCommand('cd %s; tar xvf %s; cd %s; '
                   './configure; make; sudo make install' %
                   (linux_packages.INSTALL_DIR, IPERF_TAR, IPERF_DIR))


def YumInstall(vm):
  """Installs the iperf package on the VM."""
  _Install(vm)


def AptInstall(vm):
  """Installs the iperf package on the VM."""
  _Install(vm)

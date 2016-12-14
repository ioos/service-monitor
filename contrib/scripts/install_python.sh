#!/bin/bash
set -e

echo "Downloading and installing Python-2.7.12"
curl -s 'https://www.python.org/ftp/python/2.7.12/Python-2.7.12.tgz' -o /opt/Python-2.7.12.tgz > /dev/null 2>&1
cd /opt/
# Verify file integrity
echo "- Verifying file integrity"
echo "88d61f82e3616a4be952828b3694109d Python-2.7.12.tgz" | md5sum -c --status
tar -zxf Python-2.7.12.tgz > /dev/null 2>&1
cd Python-2.7.12
echo "- Configuring Package"
./configure --prefix=/usr > /dev/null 2>&1
echo "- Compiling Package"
make > /dev/null 2>&1
echo "- Installing Package"
make install > /dev/null 2>&1
cd ..
echo "- Removing package source code"
rm -rf Python*

echo ""
echo "Downloading and installing setuptools-26.0.0"
curl -s 'https://pypi.python.org/packages/0d/13/ce6a0a22220f3da7483131bb8212d5791a03c8c3e86ff61b2c6a2de547cd/setuptools-26.0.0.tar.gz#md5=846e21fea62b9a70dfc845d70c400b7e' -o setuptools-26.0.0.tar.gz > /dev/null 2>&1
echo "- Verifying file integrity"
echo "846e21fea62b9a70dfc845d70c400b7e setuptools-26.0.0.tar.gz" | md5sum -c --status
tar -zxf setuptools-26.0.0.tar.gz > /dev/null 2>&1
cd setuptools-26.0.0
echo "- Installing package"
python setup.py install > /dev/null 2>&1
cd ..
rm -rf setuptools*
echo "- Removing source code"

echo ""
echo "Downloading and installing pip-8.1.2"
curl -s 'https://pypi.python.org/packages/e7/a8/7556133689add8d1a54c0b14aeff0acb03c64707ce100ecd53934da1aa13/pip-8.1.2.tar.gz#md5=87083c0b9867963b29f7aba3613e8f4a' -o pip-8.1.2.tar.gz > /dev/null 2>&1

echo "- Verifying file integrity"
echo "87083c0b9867963b29f7aba3613e8f4a pip-8.1.2.tar.gz" | md5sum -c --status

tar -zxf pip-8.1.2.tar.gz > /dev/null 2>&1
cd pip-8.1.2
echo "- Installing package"
python setup.py install > /dev/null 2>&1
cd ..
echo "- Removing source code"
rm -rf pip*


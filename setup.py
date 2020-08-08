from setuptools import setup, find_packages


def parse_requirements(filename):
    """ load requirements from a pip requirements file """
    lineiter = (line.strip() for line in open(filename))
    return [line for line in lineiter if line and not line.startswith("#")]


setup(name='restcelery',
      version='0.1',
      url='https://github.com/ShihHsuanChen/restcelery.git',
      author='ShihHsuanChen',
      author_email='jack072315@gmail.com',
      packages=find_packages(),
      install_requires=parse_requirements('requirements/default.txt'),
      zip_safe=False)

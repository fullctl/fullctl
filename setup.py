from setuptools import find_packages, setup


version = open('Ctl/VERSION').read().strip()
#requirements = open('Ctl/requirements.txt').read().split("\n")
#test_requirements = open('Ctl/requirements-test.txt').read().split("\n")


setup(
    name='fullctl',
    version=version,
    author='20C',
    author_email='code@20c.com',
    description='Get control',
    long_description='',
    license='LICENSE.txt',
    classifiers=[
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    #TODO
    url=None,
    download_url=None,
    #install_requires=requirements,
    #test_requires=test_requirements,
    zip_safe=True
)

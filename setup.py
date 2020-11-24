from setuptools import find_packages, setup


version = open("Ctl/VERSION").read().strip()
# requirements = open('Ctl/requirements.txt').read().split("\n")
# test_requirements = open('Ctl/requirements-test.txt').read().split("\n")


setup(
    extras_require={
        "dev": [
            "pytest>=6.0.1",
            "pytest-django>=3.8.0",
            "pytest-cov",
            "black==20.8b1",
        ]
    },
    dependency_links=[
        "https://github.com/peeringdb/peeringdb-py/archive/july_updates.zip"
    ],
    install_requires=[
        "django-handleref>=0.5",
        "djangorestframework<4,>=3.11",
        "django>=2.2,<3",
        "django-peeringdb",
        "django-reversion<4",
        "django-inet",
        "django-autocomplete-light<=4,>=3",
        "social-auth-app-django<4",
        "grainy>=1.6.0,<2",
        "django-grainy>=1.9.0,<2",
        "pyyaml",
        "pip",
        "celery<6,>=5",
    ],
    name="fullctl",
    version=version,
    author="20C",
    author_email="code@20c.com",
    description="Get control",
    long_description="",
    license="LICENSE.txt",
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
    packages=find_packages("src"),
    package_dir={"": "src"},
    include_package_data=True,
    # TODO
    url=None,
    download_url=None,
    # install_requires=requirements,
    # test_requires=test_requirements,
    zip_safe=True,
)

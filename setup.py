from setuptools import setup

import entrypoints

setup(
    name='entrypoints',
    version=entrypoints.__version__,
    author='Thomas Kluyver',
    author_email='thomas@kluyver.me.uk',
    url='https://github.com/takluyver/entrypoints',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        ],
    extras_require={
        ':python_version=="2.7"': ['configparser>=3.5'],
        },
    )

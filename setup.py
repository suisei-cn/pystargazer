#!/usr/bin/env python

from setuptools import find_packages, setup

setup(
        name='pystargazer',
        version='0.2.2',
        description='A flexible vtuber tracker.',
        author='LightQuantum',
        author_email='cy.n01@outlook.com',
        url='https://github.com/suisei-cn/pystargazer',
        packages=find_packages(),
        classifiers=[
            'License :: OSI Approved :: MIT License',
            'Programming Language :: Python :: 3',
            'Operating System :: OS Independent',
            'Development Status :: 3 - Alpha',
            'Natural Language :: Chinese (Simplified)',
            'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
            'Intended Audience :: End Users/Desktop'
        ],
        install_requires=[
            'uvloop',
            'aiohttp',
            'httpx',
            'starlette',
            'uvicorn[standard]',
            'apscheduler',
            'feedparser',
            'python-dateutil',
            'fastjsonschema'
        ],
        extras_require={
            'mongo': ['motor'],
            'files': ['tinydb==3.15.2'],
            'telemetry': ['sentry-sdk']
        },
        python_requires='>=3.8'
)

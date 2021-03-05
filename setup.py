import codecs
import re

from setuptools import setup

version_regex = r'__version__ = ["\']([^"\']*)["\']'
with open('starlette_jsonapi/__init__.py', 'r') as f:
    text = f.read()
    match = re.search(version_regex, text)

    version = match.group(1)

readme = codecs.open('README.md', encoding='utf-8').read()

setup(
    name='starlette_jsonapi',
    version=version,
    description='Tiny wrapper on starlette and marshmallow-jsonapi for fast JSON:API compliant python services.',
    author='Vlad Stefan Munteanu',
    author_email='vladstefanmunteanu@gmail.com',
    long_description=readme,
    long_description_content_type='text/markdown',
    packages=['starlette_jsonapi'],
    package_data={'starlette_jsonapi': ['LICENSE', 'README.md']},
    package_dir={'starlette_jsonapi': 'starlette_jsonapi'},
    include_package_data=True,
    install_requires=[
        'starlette>=0.14.2',
    ],
    license='MIT License',
    url='https://github.com/vladmunteanu/starlette-jsonapi',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Topic :: Internet :: WWW/HTTP',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: Implementation :: CPython',
    ],
    zip_safe=False,
)

from setuptools import find_packages, setup

setup(
    name='starlette_jsonapi',
    version='0.1',
    packages=find_packages(),
    license='BSD',
    author='Vlad Stefan Munteanu',
    url='https://github.com/vladmunteanu',
    description='Tiny wrapper on starlette and marshmallow-jsonapi for fast JSON:API compliant python services.',
    include_package_data=True,
    zip_safe=False,
)

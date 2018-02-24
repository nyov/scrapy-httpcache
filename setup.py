from os.path import dirname, join
from setuptools import setup, find_packages


with open(join(dirname(__file__), 'scrapy_httpcache/VERSION'), 'rb') as f:
    version = f.read().decode('ascii').strip()


setup(
    name='scrapy-httpcache',
    version=version,
    url='https://github.com/nyov/scrapy-httpcache',
    description='Scrapy extension to cache HTTP Requests and Responses',
    author='Scrapy developers',
    license='BSD',
    packages=find_packages(exclude=('tests', 'tests.*')),
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        'Framework :: Scrapy',
        'Development Status :: 5 - Production/Stable',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    install_requires=[
        'Scrapy>=1.0.0',
    ],
)

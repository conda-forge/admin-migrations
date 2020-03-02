from setuptools import setup, find_packages

setup(
    name="admin_migrations",
    version="0.1",
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'run-admin-migrations=admin_migrations.__main__:main',
        ],
    },
)

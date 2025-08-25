from setuptools import setup, find_packages

setup(
    name="annaws",
    version="0.1.0",
    packages=find_packages(),
    install_requires=["click", "boto3"],
    entry_points={
        "console_scripts": [
            "annaws = annaws.cli:cli", 
        ],
    },
    #python_requires=">=3.9"

)

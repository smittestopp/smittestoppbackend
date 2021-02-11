#!/usr/bin/env python

from distutils.core import setup

setup(name="Smittestopp Analytics Pipeline",
      description="Smittestopp Analytics Pipeline scripts",
      author="Smittestopp Data Analytics Team",
      packages=["corona"],
      scripts=["scripts/run_analysis_pipeline.py"],
     )

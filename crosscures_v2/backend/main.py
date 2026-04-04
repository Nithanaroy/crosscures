"""Thin wrapper for uvicorn compatibility: uvicorn main:app --reload"""
from crosscures_v2.app import app  # noqa: F401

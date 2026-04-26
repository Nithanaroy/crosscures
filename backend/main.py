"""Thin wrapper for uvicorn compatibility: uvicorn main:app --reload"""
from app.app import app  # noqa: F401

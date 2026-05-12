# LandlordAI — Claude Code Workflow

## Project Overview
Multi-agent RAG system for NYC legal violation processing.

## Agent Architecture
- Reader Agent → PDF extraction + OCR fallback
- Researcher Agent → RAG pipeline using FAISS + LangChain
- Writer Agent → Legal document generation
- Document Agent → Excel output + summons scraping

## Claude Code Instructions
- Always use async def for FastAPI endpoints
- Wrap all LLM calls in try-catch with 3 retries
- Return structured JSON only — no markdown
- Use Pydantic models for all input validation
- Agent prompts live in /prompts folder — never hardcode

## Tech Stack
Python · LangChain · FastAPI · FAISS · 
OpenAI API · Streamlit · PyMuPDF · Tesseract OCR

## Coding Patterns
- All agents follow single responsibility principle
- Error handling — graceful degradation always
- Low temperature (0.1-0.2) for all legal document generation

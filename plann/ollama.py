#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ollama integration for plann
Allows adding events and tasks using natural language
"""

import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
import re


class OllamaClient:
    """Client for interacting with Ollama API"""

    def __init__(self, base_url: str = "http://localhost:11434"):
        """
        Initialize Ollama client

        Args:
            base_url: Base URL for Ollama API (default: http://localhost:11434)
        """
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/api"

    def is_available(self) -> bool:
        """Check if Ollama is running and available"""
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def list_models(self) -> List[str]:
        """List available models"""
        try:
            response = requests.get(f"{self.api_url}/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model['name'] for model in data.get('models', [])]
            return []
        except requests.RequestException:
            return []

    def generate(self, prompt: str, model: str = "llama2", stream: bool = False) -> Dict[str, Any]:
        """
        Generate text using Ollama

        Args:
            prompt: The prompt to send to the model
            model: Model name to use (default: llama2)
            stream: Whether to stream the response

        Returns:
            Dictionary containing the response
        """
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
            "format": "json"
        }

        try:
            response = requests.post(
                f"{self.api_url}/generate",
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                if stream:
                    return {"response": response.text}
                else:
                    return response.json()
            else:
                return {
                    "error": f"HTTP {response.status_code}: {response.text}",
                    "response": ""
                }
        except requests.RequestException as e:
            return {
                "error": f"Request failed: {str(e)}",
                "response": ""
            }


class NaturalLanguageParser:
    """Parse natural language into calendar events and tasks"""

    def __init__(self, ollama_client: OllamaClient, model: str = "llama2"):
        """
        Initialize parser

        Args:
            ollama_client: OllamaClient instance
            model: Model to use for parsing
        """
        self.ollama = ollama_client
        self.model = model

    def parse_event(self, text: str) -> Dict[str, Any]:
        """
        Parse natural language text into event/task information.

        Args:
            text: Natural language text (example: "Dentist appointment tomorrow at 14h")

        Returns:
            Dictionary with parsed information:
            {
                "type": "event" or "todo",
                "summary": "description",
                "date": "YYYY-MM-DD",
                "time": "HH:MM" (optional),
                "duration": "2h" (optional),
                "due_date": "YYYY-MM-DD" (for tasks),
                "priority": 1-9 (for tasks, plann uses 1-9),
                "alarm": "1h" (optional)
            }
        """
        today = datetime.now().strftime("%Y-%m-%d")

        prompt = f"""You are an assistant that extracts structured data from natural language in order to build calendar events or tasks.

Today: {today}

Text: "{text}"

Return a JSON object with the keys below:
- "type": "event" (appointment, meeting) or "todo" (task)
- "summary": short description
- "date": YYYY-MM-DD (resolve relative expressions such as "tomorrow")
- "time": HH:MM (24h clock, optional)
- "duration": e.g. "1h", "30m", "2h30m" (optional)
- "due_date": YYYY-MM-DD for tasks (optional)
- "priority": value 1 (high) to 9 (low) when provided or implied
- "alarm": reminder such as "1h", "30m", "1d" (optional)
- "location": location or address when the text contains one

Examples:
"Dentist appointment tomorrow at 14h" -> {{"type": "event", "summary": "Dentist appointment", "date": "2025-10-23", "time": "14:00", "location": "Dental clinic"}}
"Team meeting Monday 10h for two hours" -> {{"type": "event", "summary": "Team meeting", "date": "2025-10-27", "time": "10:00", "duration": "2h"}}
"Buy bread" -> {{"type": "todo", "summary": "Buy bread", "priority": 5}}
"Finish the report by Friday" -> {{"type": "todo", "summary": "Finish the report", "due_date": "2025-10-24", "priority": 3}}
"Call Marie the day after tomorrow" -> {{"type": "todo", "summary": "Call Marie", "due_date": "2025-10-24", "priority": 5}}

Return JSON only."""

        result = self.ollama.generate(prompt, model=self.model)

        if "error" in result:
            raise Exception(f"Ollama error: {result['error']}")

        # Extract JSON from response
        response_text = result.get("response", "")

        try:
            # Try to parse directly
            parsed = json.loads(response_text)
        except json.JSONDecodeError:
            # Try to find JSON in the response
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                parsed = json.loads(json_match.group(0))
            else:
                # Fallback: basic parsing
                parsed = self._fallback_parse(text)

        return parsed

    def _fallback_parse(self, text: str) -> Dict[str, Any]:
        """
        Fallback parsing when Ollama fails
        Uses simple heuristics
        """
        text_lower = text.lower()

        # Determine type
        task_keywords = ['acheter', 'faire', 'finir', 'appeler', 'envoyer', 'tache', 'todo']
        normalized = (
            text_lower
            .replace('\\u00e0', 'a')
            .replace('\\u00e1', 'a')
            .replace('\\u00e2', 'a')
            .replace('\\u00e8', 'e')
            .replace('\\u00e9', 'e')
            .replace('\\u00ea', 'e')
            .replace('\\u00eb', 'e')
            .replace('\\u00ee', 'i')
            .replace('\\u00ef', 'i')
            .replace('\\u00f4', 'o')
            .replace('\\u00f6', 'o')
            .replace('\\u00f9', 'u')
            .replace('\\u00fb', 'u')
        )
        is_task = any(keyword in normalized for keyword in task_keywords)

        result = {
            "type": "todo" if is_task else "event",
            "summary": text,
            "priority": 5,  # Default priority for plann (1-9 scale)
            "location": None
        }

        # Try to extract date
        today = datetime.now()

        if "demain" in normalized:
            result["date"] = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        elif "apres-demain" in normalized.replace(' ', '-'):
            result["date"] = (today + timedelta(days=2)).strftime("%Y-%m-%d")
        elif "aujourd'hui" in text_lower or "aujourdhui" in normalized:
            result["date"] = today.strftime("%Y-%m-%d")

        # Try to extract time (HH:MM or HHh or HHhMM)
        time_pattern = r'(\d{1,2})[h:](\d{2})?'
        time_match = re.search(time_pattern, text)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2)) if time_match.group(2) else 0
            result["time"] = f"{hour:02d}:{minute:02d}"

        # Naive location extraction (after " a ", " au ", " chez ", etc.)
        location_markers = [' \u00e0 ', ' a ', ' au ', ' chez ', ' en ', ' sur ']
        for marker in location_markers:
            if marker in text_lower:
                idx = text_lower.find(marker)
                location_candidate = text[idx + len(marker):].strip()
                if location_candidate:
                    result["location"] = location_candidate
                break

        return result


def format_for_plann(parsed_data: Dict[str, Any]) -> tuple:
    """
    Convert parsed data into plann command format

    Args:
        parsed_data: Dictionary from parse_event()

    Returns:
        Tuple of (command_name, timespec, summary, kwargs)
        - command_name: "add" for both events and todos
        - timespec: time specification string for events (None for todos)
        - summary: event/task summary
        - kwargs: dict of additional parameters
    """
    event_type = parsed_data.get("type", "event")
    summary = parsed_data.get("summary", "Event" if event_type == "event" else "Task")
    kwargs = {}

    if event_type == "event":
        # Build timespec string for events
        date = parsed_data.get("date", "")
        time = parsed_data.get("time", "")
        duration = parsed_data.get("duration", "")

        if date and time:
            timespec = f"{date}T{time}"
            if duration:
                timespec += f"+{duration}"
            else:
                # Default 1 hour duration if not specified
                timespec += "+1h"
        elif date:
            # Full day event
            timespec = date
        else:
            # Default to today
            timespec = "today"

        kwargs['event'] = True

        # Add alarm if specified
        if parsed_data.get("alarm"):
            kwargs['alarm'] = parsed_data["alarm"]

        # Add location if provided
        if parsed_data.get("location"):
            kwargs['set_location'] = parsed_data["location"]

    else:  # todo
        timespec = None
        kwargs['todo'] = True

        # Set due date
        if parsed_data.get("due_date"):
            kwargs['set_due'] = parsed_data["due_date"]

        # Set priority (plann uses 1-9 scale)
        if parsed_data.get("priority"):
            kwargs['set_priority'] = int(parsed_data["priority"])

        # Add alarm if specified
        if parsed_data.get("alarm"):
            kwargs['set_alarm'] = parsed_data["alarm"]

    return ("add", timespec, summary, kwargs)


def test_ollama_connection():
    """Test function to check Ollama availability"""
    client = OllamaClient()

    print("Testing Ollama connection...")
    if client.is_available():
        print("[OK] Ollama is running")
        models = client.list_models()
        if models:
            print(f"[OK] Available models: {', '.join(models)}")
        else:
            print("[WARN] No models found. Install a model with: ollama pull llama2")
        return True
    else:
        print("[ERR] Ollama is not running or not accessible")
        print("  Start it with: ollama serve")
        return False


if __name__ == "__main__":
    # Simple test
    test_ollama_connection()

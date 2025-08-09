"""
Agentic Picker Module

This module provides AI-powered file analysis capabilities for the gitex tool.
It includes:
- Configuration management for LLM connections
- Interactive mode for file selection and AI summarization
- Support for various OpenAI-compatible API endpoints

Key Components:
- AgenticConfig: Manages persistent configuration for LLM settings
- LLMClient: Generic client for OpenAI-compatible chat completion APIs
- AgenticPicker: Main picker class that integrates with textual UI for file selection

IMPORTANT NOTE about exit behavior:
When users select "Exit" from the agentic mode menu, the program terminates completely
using sys.exit(0). 
"""

from typing import List, Optional, Dict, Any
import json
import requests
import os
import sys  # Required for clean program termination in interactive mode
from pathlib import Path
from gitex.models import FileNode
from gitex.picker.base import Picker, DefaultPicker
from gitex.picker.textuals import TextualPicker


class AgenticConfig:
    """
    Manages agentic picker configuration.
    
    Handles persistent storage of LLM connection settings including:
    - API keys
    - Base URLs for different providers (OpenAI, Anthropic, local servers)
    - Model names
    
    Configuration is stored in ~/.gitex/config.json for persistence across sessions.
    """
    
    def __init__(self):
        self.config_path = Path.home() / '.gitex' / 'config.json'
        self.config_path.parent.mkdir(exist_ok=True)
    
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {}
    
    def save_config(self, config: Dict[str, Any]):
        """Save configuration to file."""
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def setup_interactive(self) -> Dict[str, str]:
        """Interactive setup for first-time users."""
        print("🤖 Agentic Mode Setup")
        print("Configure your LLM connection:")
        
        api_key = input("API Key: ").strip()
        base_url = input("Base URL (default: https://api.openai.com/v1): ").strip()
        if not base_url:
            base_url = "https://api.openai.com/v1"
        
        model = input("Model (default: gpt-3.5-turbo): ").strip()
        if not model:
            model = "gpt-3.5-turbo"
        
        config = {
            'api_key': api_key,
            'base_url': base_url,
            'model': model
        }
        
        self.save_config(config)
        print("✅ Configuration saved!")
        return config
    
    def modify_config(self):
        """Modify existing configuration."""
        config = self.load_config()
        print("Current configuration:")
        print(f"API Key: {'*' * (len(config.get('api_key', '')) - 4) + config.get('api_key', '')[-4:]}")
        print(f"Base URL: {config.get('base_url', 'Not set')}")
        print(f"Model: {config.get('model', 'Not set')}")
        
        print("\nEnter new values (press Enter to keep current):")
        
        new_key = input("New API Key: ").strip()
        if new_key:
            config['api_key'] = new_key
        
        new_url = input("New Base URL: ").strip()
        if new_url:
            config['base_url'] = new_url
            
        new_model = input("New Model: ").strip()
        if new_model:
            config['model'] = new_model
        
        self.save_config(config)
        print("✅ Configuration updated!")


class LLMClient:
    """
    Generic LLM client supporting OpenAI-compatible APIs.
    
    This client can work with:
    - OpenAI API (default)
    - Anthropic API (with compatible base_url)
    - Local LLM servers (like ollama, LM Studio)
    - Any service that implements OpenAI chat completions format
    
    Handles HTTP requests, error responses, and timeout management.
    """
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-3.5-turbo"):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def chat_completion(self, messages: List[Dict[str, str]], max_tokens: int = 1000) -> str:
        """Send chat completion request to LLM."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.3
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers=self.headers,
                json=payload,
                timeout=30
            )
            
            if not response.ok:
                print(f"API Error {response.status_code}: {response.text}")
                return f"API Error: {response.status_code} - {response.text[:200]}"
            
            data = response.json()
            return data['choices'][0]['message']['content'].strip()
        except Exception as e:
            print(f"Full error details: {e}")
            return f"Error: {str(e)}"


class AgenticPicker(Picker):
    """
    AI-powered picker that can summarize files and find related content.
    
    
    The main entry point is run_interactive_mode() which presents a menu-driven
    interface for users to select files and get AI analysis.
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None, ignore_hidden: bool = True, respect_gitignore: bool = False):
        self.llm_client = llm_client
        self.base_picker = DefaultPicker(ignore_hidden, respect_gitignore)
        self.config = AgenticConfig()
        self._file_cache: Dict[str, str] = {}
        
        # Initialize LLM client if not provided
        if not self.llm_client:
            config = self.config.load_config()
            if not config or not config.get('api_key'):
                config = self.config.setup_interactive()
            
            self.llm_client = LLMClient(
                api_key=config['api_key'],
                base_url=config['base_url'],
                model=config['model']
            )
    
    def run_interactive_mode(self, nodes: List[FileNode]) -> List[FileNode]:
        """
        Interactive agentic mode with menu options.
        
        This method presents a loop-based menu for AI-powered file analysis:
        1. File summarization with interactive selection
        2. Configuration management
        3. Exit (terminates entire program)
        
        Note: This is designed as a terminal operation - when user exits,
        the entire program should terminate rather than continue with normal CLI flow.
        """
        while True:
            print("\n🤖 Agentic Mode")
            print("1. Summarize selected files (with interactive selection)")
            print("2. Modify configuration")
            print("3. Exit")
            
            choice = input("Choose option (1-3): ").strip()
            
            if choice == "1":
                print("\n### Interactive File Selection ###")
                
                # Use TextualPicker for interactive file selection UI
                # This provides a tree-based checkbox interface for users
                interactive_picker = TextualPicker(ignore_hidden=True, respect_gitignore=True)
                
                # Determine root path from the provided nodes
                # Handle both directory and file node scenarios
                root_path = nodes[0].path if nodes else "."
                if nodes and nodes[0].node_type == "file":
                    root_path = os.path.dirname(nodes[0].path)
                
                # Let user select files through interactive UI
                selected_nodes = interactive_picker.pick(root_path)
                
                if selected_nodes:
                    # Display selected files for confirmation
                    print("\n### Selected Files ###")
                    for node in self._collect_files(selected_nodes):
                        print(f"📄 {node.path}")
                    
                    # Generate and display AI-powered summary
                    print("\n### AI Summary ###")
                    summary = self.summarize_files(selected_nodes)
                    print(summary)
                else:
                    print("No files selected.")
            
            elif choice == "2":
                # Allow user to modify LLM configuration (API key, model, etc.)
                self.config.modify_config()
                
                # Reload LLM client with updated configuration
                # This ensures changes take effect immediately
                config = self.config.load_config()
                self.llm_client = LLMClient(
                    api_key=config['api_key'],
                    base_url=config['base_url'],
                    model=config['model']
                )
                print("Configuration updated!")
            
            elif choice == "3":
                # IMPORTANT: Exit terminates the entire program
                # This prevents the main CLI from continuing to render trees
                # Previous bug: returning nodes here caused main.py to continue execution
                print("Goodbye! 👋")
                sys.exit(0)  # Clean program termination
            
            else:
                print("Invalid choice. Please select 1-3.")
        
        # This line should never be reached due to sys.exit(0) above
        # Keeping it for completeness and type hints
        return nodes
    
    def pick(self, root_path: str) -> List[FileNode]:
        """Standard picker interface - returns all files for now."""
        return self.base_picker.pick(root_path)
    
    def summarize_files(self, file_nodes: List[FileNode]) -> str:
        """
        Generate AI-powered summary of selected files.
        
        Process:
        1. Collect file contents from all selected file nodes
        2. Truncate content to first 2000 chars per file (to fit in LLM context)
        3. Send to LLM with specialized prompt for code analysis
        4. Return structured summary focusing on purpose and architecture
        
        The LLM is instructed to provide:
        - First paragraph: Goal and purpose of the code
        - Second paragraph: Classes, functions, and their relationships
        
        Args:
            file_nodes: List of FileNode objects to analyze
            
        Returns:
            String containing AI-generated summary or error message
        """
        if not file_nodes:
            return "No files selected."
        
        # Collect file info
        file_info = []
        for node in self._collect_files(file_nodes):
            content = self._get_file_content(node.path)
            if content and not content.startswith("<Error"):
                file_info.append(f"## {node.name}\nPath: {node.path}\n```\n{content[:2000]}...\n```")
        
        if not file_info:
            return "No readable files found."
        
        files_text = "\n\n".join(file_info[:10])  # Limit to 10 files
        
        messages = [
            {"role": "system", "content": """You are a summarize agent which helps developers understand their files and code better. Your job is to write a simple and enhanced report of files in this format:

In the first paragraph, you will talk about the goal and purpose of the code - what problem it solves, what functionality it provides, and its overall objective.

In the second paragraph, write about classes and functions and their jobs - describe the main classes, their responsibilities, key methods, their inputs and outputs, and how they work together.

Keep the summary clear, concise, and focused on helping developers quickly understand the codebase structure and purpose."""},
            {"role": "user", "content": f"Analyze these files:\n\n{files_text}"}
        ]
        
        return self.llm_client.chat_completion(messages, max_tokens=1500)
    
    def _collect_files(self, nodes: List[FileNode]) -> List[FileNode]:
        """Recursively collect all file nodes."""
        files = []
        for node in nodes:
            if node.node_type == "file":
                files.append(node)
            if node.children:
                files.extend(self._collect_files(node.children))
        return files
    
    def _get_file_content(self, path: str) -> str:
        """Get file content with caching."""
        if path in self._file_cache:
            return self._file_cache[path]
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._file_cache[path] = content
            return content
        except Exception as e:
            return f"<Error reading file: {e}>"
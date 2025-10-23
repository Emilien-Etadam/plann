#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Minimal GUI for plann with Ollama integration
A small, always-on-top window for quick event/task entry
"""

from tkinter import messagebox
import customtkinter as ctk
import threading
from datetime import datetime
import sys
import os
import json
import time
import queue

from plann.ollama import OllamaClient, NaturalLanguageParser, format_for_plann
from plann.config import read_config, expand_config_section, config_section
from plann.lib import find_calendars
from plann.commands import _add_event, _add_todo

ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


class ConfigDialog:
    """Configuration dialog for CalDAV settings"""

    def __init__(self, parent=None, initial_config=None, config_path=None):
        self.result = None
        self.is_active = True
        self.ui_queue = queue.Queue()
        self.initial_config = initial_config or {}
        self.config_path = config_path or os.path.expanduser("~/.config/calendar.conf")

        # Create dialog window
        if parent:
            self.dialog = ctk.CTkToplevel(parent)
        else:
            self.dialog = ctk.CTk()

        self.dialog.title("Config")
        self.dialog.geometry("380x320")
        self.dialog.resizable(False, False)

        # Center window
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (380 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (320 // 2)
        self.dialog.geometry(f"+{x}+{y}")

        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", self.on_close)

        self.create_widgets()

        # Make modal
        if parent:
            self.dialog.transient(parent)
            self.dialog.grab_set()

        # Start processing UI updates from queue
        self._process_ui_queue()

    def create_widgets(self):
        """Create configuration form widgets"""
        main_frame = ctk.CTkFrame(self.dialog, corner_radius=0, fg_color=("white", "#1f1f1f"))
        main_frame.pack(fill="both", expand=True, padx=16, pady=16)

        title = ctk.CTkLabel(
            main_frame,
            text="Reglages CalDAV",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(pady=(10, 4))

        subtitle = ctk.CTkLabel(
            main_frame,
            text="Connecte plann a ton serveur CalDAV.\nLes champs marques d'un asterisk sont requis.",
            font=ctk.CTkFont(size=12),
            justify="center"
        )
        subtitle.pack(pady=(0, 12))

        form_frame = ctk.CTkFrame(main_frame, corner_radius=0, fg_color=("white", "#1f1f1f"))
        form_frame.pack(fill="both", expand=True, padx=10, pady=6)
        form_frame.grid_columnconfigure(1, weight=1)

        label_font = ctk.CTkFont(size=13)

        # CalDAV URL
        ctk.CTkLabel(form_frame, text="\U0001F517", anchor="w", font=label_font).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 6))
        self.url_entry = ctk.CTkEntry(form_frame, width=230, corner_radius=0)
        self.url_entry.grid(row=0, column=1, sticky="ew", padx=12, pady=(12, 6))
        self.url_entry.insert(0, self.initial_config.get('caldav_url', 'https://'))

        # Username
        ctk.CTkLabel(form_frame, text="\U0001F464", anchor="w", font=label_font).grid(row=1, column=0, sticky="w", padx=12, pady=6)
        self.user_entry = ctk.CTkEntry(form_frame, width=230, corner_radius=0)
        self.user_entry.grid(row=1, column=1, sticky="ew", padx=12, pady=6)
        self.user_entry.insert(0, self.initial_config.get('caldav_user', ''))

        # Password
        ctk.CTkLabel(form_frame, text="\U0001F512", anchor="w", font=label_font).grid(row=2, column=0, sticky="w", padx=12, pady=6)
        self.pass_entry = ctk.CTkEntry(form_frame, width=230, show="\u2022", corner_radius=0)
        self.pass_entry.grid(row=2, column=1, sticky="ew", padx=12, pady=6)

        # Ollama host
        ctk.CTkLabel(form_frame, text="\U0001F5A5", anchor="w", font=label_font).grid(row=3, column=0, sticky="w", padx=12, pady=6)
        self.ollama_host_entry = ctk.CTkEntry(form_frame, width=230, corner_radius=0)
        self.ollama_host_entry.grid(row=3, column=1, sticky="ew", padx=12, pady=6)
        self.ollama_host_entry.insert(0, self.initial_config.get('ollama_host', 'http://localhost:11434'))

        # Ollama model
        ctk.CTkLabel(form_frame, text="\U0001F9E0", anchor="w", font=label_font).grid(row=4, column=0, sticky="w", padx=12, pady=6)
        self.ollama_model_entry = ctk.CTkEntry(form_frame, width=230, corner_radius=0)
        self.ollama_model_entry.grid(row=4, column=1, sticky="ew", padx=12, pady=6)
        self.ollama_model_entry.insert(0, self.initial_config.get('ollama_model', 'llama2'))

        # Test result label
        self.test_result_label = ctk.CTkLabel(
            form_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("gray20", "gray80")
        )
        self.test_result_label.grid(row=5, column=0, columnspan=2, pady=(10, 6))

        # Buttons frame
        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=(6, 0))

        # Test button
        self.test_button = ctk.CTkButton(
            button_frame,
            text="Tester",
            width=90,
            command=self.test_connection,
            corner_radius=0
        )
        self.test_button.pack(side="left", padx=4)

        # Save button
        self.save_button = ctk.CTkButton(
            button_frame,
            text="Enregistrer",
            width=110,
            command=self.save_config,
            corner_radius=0
        )
        self.save_button.pack(side="left", padx=4)

        # Cancel button
        ctk.CTkButton(
            button_frame,
            text="Fermer",
            fg_color="transparent",
            hover_color=("#d0d0d0", "#2a2a2a"),
            text_color=("black", "white"),
            command=self.on_close,
            corner_radius=0
        ).pack(side="left", padx=4)

    def test_connection(self):
        """Test CalDAV connection"""
        url = self.url_entry.get().strip()
        user = self.user_entry.get().strip()
        password = self.pass_entry.get()

        if not url or not user or not password:
            self.test_result_label.configure(
                text="[X] Renseignez les champs requis",
                text_color="#ff3b30"
            )
            return

        print("\n" + "="*50)
        print("[DEBUG] Starting connection test...")
        print("="*50)

        self.test_button.configure(state="disabled", text="Analyse...")
        self.test_result_label.configure(text="[...] Test de connexion...", text_color="#ff9f0a")
        self.dialog.update()

        # Test in background
        threading.Thread(target=self._test_connection_thread, args=(url, user, password), daemon=True).start()

    def _test_connection_thread(self, url, user, password):
        """Test connection in background thread"""
        print(f"[DEBUG] Testing connection to: {url}")
        print(f"[DEBUG] User: {user}")

        try:
            import caldav
            import socket

            # Set a timeout for socket operations
            socket.setdefaulttimeout(10)

            print("[DEBUG] Creating CalDAV client...")

            # Try to connect with timeout
            client = caldav.DAVClient(
                url=url,
                username=user,
                password=password
            )

            print("[DEBUG] Getting principal...")
            principal = client.principal()

            print("[DEBUG] Getting calendars...")
            calendars = principal.calendars()

            print(f"[DEBUG] Found {len(calendars)} calendar(s)")

            if calendars:
                self._safe_update_widget(
                    lambda: self.test_result_label.configure(
                        text=f"[OK] Connexion reussie ! {len(calendars)} calendrier(s) trouve(s)",
                        text_color="#34c759"
                    )
                )
            else:
                self._safe_update_widget(
                    lambda: self.test_result_label.configure(
                        text="[!] Connexion OK mais aucun calendrier trouve",
                        text_color="#ff9f0a"
                    )
                )

        except socket.timeout:
            print("[DEBUG] Connection timeout!")
            self._safe_update_widget(
                lambda: self.test_result_label.configure(
                    text="[X] Timeout : Le serveur ne repond pas (10s)",
                    text_color="#ff3b30"
                )
            )

        except Exception as e:
            print(f"[DEBUG] Error: {type(e).__name__}: {str(e)}")
            error_msg = str(e)
            if len(error_msg) > 80:
                error_msg = error_msg[:80] + "..."
            self._safe_update_widget(
                lambda: self.test_result_label.configure(
                    text=f"[X] Erreur : {error_msg}",
                    text_color="#ff3b30"
                )
            )

        finally:
            print("[DEBUG] Test finished")
            self._safe_update_widget(
                lambda: self.test_button.configure(state="normal", text="Tester")
            )

    def _safe_update_widget(self, callback):
        """Safely update widget from background thread"""
        if self.is_active:
            try:
                self.ui_queue.put(callback)
            except:
                pass  # Dialog may have been closed

    def _process_ui_queue(self):
        """Process UI updates from queue (runs in main thread)"""
        try:
            while True:
                # Get all pending callbacks
                callback = self.ui_queue.get_nowait()
                try:
                    callback()
                except Exception as e:
                    print(f"[DEBUG] Error in UI callback: {e}")
        except queue.Empty:
            pass

        # Schedule next check if still active
        if self.is_active:
            self.dialog.after(100, self._process_ui_queue)

    def save_config(self):
        """Save configuration to file"""
        print("\n" + "="*50)
        print("[DEBUG] Saving configuration...")
        print("="*50)

        url = self.url_entry.get().strip()
        user = self.user_entry.get().strip()
        password = self.pass_entry.get()
        ollama_host = self.ollama_host_entry.get().strip()
        ollama_model = self.ollama_model_entry.get().strip()
        section = "default"  # Always use 'default' section

        print(f"[DEBUG] URL: {url}")
        print(f"[DEBUG] User: {user}")
        print(f"[DEBUG] Ollama host: {ollama_host}")
        print(f"[DEBUG] Ollama model: {ollama_model}")
        print(f"[DEBUG] Section: {section}")

        if not url or not user:
            print("[DEBUG] Missing fields!")
            messagebox.showerror(
                "Missing fields",
                "Provide at least URL and user."
            )
            return

        # Config file path
        config_path = self.config_path
        config_dir = os.path.dirname(config_path)

        print(f"[DEBUG] Config path: {config_path}")
        print(f"[DEBUG] Config dir: {config_dir}")

        # Create config directory if needed
        if not os.path.exists(config_dir):
            print(f"[DEBUG] Creating config directory...")
            try:
                os.makedirs(config_dir)
                print(f"[DEBUG] Directory created successfully")
            except Exception as e:
                print(f"[DEBUG] Error creating directory: {e}")
                messagebox.showerror(
                    "Erreur",
                    f"Impossible de creer le repertoire de configuration:\n{e}"
                )
                return
        else:
            print(f"[DEBUG] Config directory already exists")

        # Load existing config or create new
        config = {}
        existing_section = {}
        if os.path.exists(config_path):
            print(f"[DEBUG] Loading existing config...")
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                print(f"[DEBUG] Existing config loaded: {list(config.keys())}")
                existing_section = config.get(section, {}).copy()

                # Backup existing file
                backup_path = f"{config_path}.{int(time.time())}.bak"
                print(f"[DEBUG] Creating backup at: {backup_path}")
                os.rename(config_path, backup_path)
            except Exception as e:
                print(f"[DEBUG] Error loading config: {e}")
                messagebox.showerror(
                    "Erreur",
                    f"Impossible de lire la configuration existante:\n{e}"
                )
                return
        else:
            print(f"[DEBUG] No existing config, creating new")

        # Add new section
        print(f"[DEBUG] Adding section '{section}' to config")
        updated_section = existing_section.copy()
        updated_section["caldav_url"] = url
        updated_section["caldav_user"] = user

        if password:
            updated_section["caldav_pass"] = password
        elif "caldav_pass" not in updated_section:
            messagebox.showerror(
                "Missing password",
                "Enter the CalDAV password at least once."
            )
            return

        if ollama_host:
            updated_section["ollama_host"] = ollama_host
        elif "ollama_host" in updated_section:
            del updated_section["ollama_host"]

        if ollama_model:
            updated_section["ollama_model"] = ollama_model
        elif "ollama_model" in updated_section:
            del updated_section["ollama_model"]

        config[section] = updated_section

        # Save config
        print(f"[DEBUG] Writing config to file...")
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=4)
            print(f"[DEBUG] Config written successfully!")

            messagebox.showinfo(
                "Configuration saved",
                f"Config stored in:\n{config_path}\n\n"
                f"Section: {section}"
            )

            self.result = config
            self.on_close()

        except Exception as e:
            messagebox.showerror(
                "Save error",
                f"Unable to save configuration:\n{e}"
            )

    def on_close(self):
        """Handle dialog close"""
        self.is_active = False
        try:
            self.dialog.destroy()
        except:
            pass

    def show(self):
        """Show dialog and wait for result"""
        self.dialog.wait_window()
        return self.result


class PlannGUI:
    """Minimal GUI for plann"""

    def __init__(self, config_section='default', model='llama2', ollama_host='http://localhost:11434'):
        self.config_section = config_section
        self.model = model
        self.ollama_host = ollama_host
        self.config_path = os.path.expanduser("~/.config/calendar.conf")
        self.config = {}
        self.section_names = []
        self.calendars = []
        self.event_calendars = []
        self.todo_calendars = []
        self._calendar_urls = set()
        self.config_loaded = False
        self.ollama = None
        self.parser = None
        self.ollama_available = False
        self.history_visible = True
        self.current_height = 0

        # Create main window
        self.root = ctk.CTk()
        self.root.title("plann")

        # Set window size and position
        self.window_width = 380
        self.expanded_height = 360
        self.compact_height = 240

        # Position in top-right corner
        screen_width = self.root.winfo_screenwidth()
        x = screen_width - self.window_width - 24
        y = 28

        self.root.geometry(f"{self.window_width}x{self.expanded_height}+{x}+{y}")
        self.root.minsize(self.window_width, self.compact_height)
        self.current_height = self.expanded_height

        # Always on top
        self.root.attributes('-topmost', True)

        # State flag for pending operations
        self.processing = False

        # Create UI
        self.create_widgets()

        # Load config and calendars
        self.config_loaded = self.load_config()

        # Update UI based on configuration status
        self.update_ui_state()
        self.init_ollama()
        self.update_status()

    def create_widgets(self):
        """Create GUI widgets"""
        main_frame = ctk.CTkFrame(self.root, corner_radius=0, fg_color=("white", "#1e1e1e"))
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)

        status_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        status_row.pack(fill="x", padx=18, pady=(12, 6))
        status_row.grid_columnconfigure(1, weight=1)

        self.llm_icon = ctk.CTkLabel(status_row, text="[]", width=24)
        self.llm_icon.grid(row=0, column=0, padx=(0, 8), sticky="w")

        self.status_label = ctk.CTkLabel(status_row, text="", font=ctk.CTkFont(size=12))
        self.status_label.grid(row=0, column=1, sticky="w")

        self.text_input = ctk.CTkTextbox(
            main_frame,
            height=90,
            border_width=0,
            corner_radius=0,
            font=ctk.CTkFont(size=13),
            wrap="word"
        )
        self.text_input.pack(fill="x", padx=18, pady=(4, 10))
        self.text_input.bind('<Return>', self.on_enter_key)
        self.text_input.focus_set()

        buttons_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=18, pady=(0, 10))

        self.voice_button = ctk.CTkButton(
            buttons_frame,
            text="\U0001F3A4",
            command=self.voice_input,
            height=32,
            width=44,
            corner_radius=0,
            fg_color="#d5d5d5",
            hover_color="#c0c0c0",
            text_color="black"
        )
        self.voice_button.pack(side="left")

        self.history_label = ctk.CTkLabel(main_frame, text="\U0001F5C2", font=ctk.CTkFont(size=16))
        self.history_label.pack(anchor="w", padx=18, pady=(0, 4))

        # History text area with scrollbar
        self.history_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.history_container.pack(fill="both", expand=True, padx=12, pady=(0, 6))
        self.history_container.grid_columnconfigure(0, weight=1)
        self.history_container.grid_rowconfigure(0, weight=1)

        self.history_text = ctk.CTkTextbox(
            self.history_container,
            height=200,
            wrap="word",
            font=ctk.CTkFont(family="SF Mono", size=12),
            corner_radius=0,
            border_width=0
        )
        self.history_text.grid(row=0, column=0, sticky="nsew")
        self.history_text.configure(state="disabled")

        history_scroll = ctk.CTkScrollbar(
            self.history_container,
            command=self.history_text.yview
        )
        history_scroll.grid(row=0, column=1, sticky="ns", padx=(6, 0))
        self.history_text.configure(yscrollcommand=history_scroll.set)

        # Configure tags for colored output
        self.history_text.tag_config('success', foreground='#34c759')
        self.history_text.tag_config('error', foreground='#ff3b30')
        self.history_text.tag_config('info', foreground='#0a84ff')
        self.history_text.tag_config('time', foreground='#8e8e93')

        # Bottom frame with options
        self.bottom_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        self.bottom_frame.pack(fill="x", padx=18, pady=(8, 4))

        self.toggle_history_button = ctk.CTkButton(
            self.bottom_frame,
            text="\u25BC",
            height=26,
            width=32,
            command=self.toggle_history,
            fg_color="transparent",
            hover_color=("gray80", "#3a3a3a"),
            text_color=("black", "white"),
            corner_radius=0
        )
        self.toggle_history_button.pack(side="left")

        self.always_on_top_var = ctk.BooleanVar(value=True)
        self.pin_label = ctk.CTkLabel(self.bottom_frame, text="^", font=ctk.CTkFont(size=14))
        self.pin_label.pack(side="left", padx=(12, 4))

        self.always_on_top_checkbox = ctk.CTkCheckBox(
            self.bottom_frame,
            text="",
            variable=self.always_on_top_var,
            command=self.toggle_always_on_top,
            corner_radius=0,
            width=18,
            height=18,
            border_width=1
        )
        self.always_on_top_checkbox.pack(side="left")

        right_btn_frame = ctk.CTkFrame(self.bottom_frame, fg_color="transparent")
        right_btn_frame.pack(side="right")

        self.config_button = ctk.CTkButton(
            right_btn_frame,
            text="\u2699",
            width=38,
            height=26,
            command=self.open_config_dialog,
            corner_radius=0,
            fg_color="transparent",
            hover_color=("gray80", "#3a3a3a"),
            text_color=("black", "white")
        )
        self.config_button.pack(side="right", padx=(6, 0))

        self.clear_button = ctk.CTkButton(
            right_btn_frame,
            text="\U0001F9F9",
            width=38,
            height=26,
            command=self.clear_history,
            corner_radius=0,
            fg_color="transparent",
            hover_color=("gray80", "#3a3a3a"),
            text_color=("black", "white")
        )
        self.clear_button.pack(side="right")

    def _register_calendars(self, calendars):
        """Register discovered calendars and classify them."""
        for cal in calendars:
            url = getattr(cal, 'url', '') or ''
            if url in self._calendar_urls:
                continue

            if url:
                self._calendar_urls.add(url)

            self.calendars.append(cal)

            try:
                components = cal.get_supported_components() or []
            except Exception:
                components = []

            components = [c.lower() for c in components]
            url_lower = url.lower()

            supports_todo = 'vtodo' in components or 'task' in url_lower or 'todo' in url_lower
            supports_event = 'vevent' in components or (not components and not supports_todo)

            # Si la collection est identifiee comme liste de taches, on evite de la
            # classer cote evenements meme si le serveur annonce VEVENT pour limiter
            # les doublons lors des creations.
            if supports_todo and ('task' in url_lower or 'todo' in url_lower):
                supports_event = False

            if supports_todo and cal not in self.todo_calendars:
                self.todo_calendars.append(cal)
            if supports_event and cal not in self.event_calendars:
                self.event_calendars.append(cal)

    def adjust_geometry(self, height):
        """Update window geometry while keeping screen position"""
        self.current_height = max(self.compact_height, min(height, self.expanded_height))
        self.root.update_idletasks()
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        self.root.geometry(f"{self.window_width}x{self.current_height}+{x}+{y}")

    def toggle_history(self):
        """Toggle history visibility and window height"""
        self.history_visible = not self.history_visible

        if self.history_visible:
            self.history_label.pack(anchor='w', padx=18, pady=(0, 4), before=self.bottom_frame)
            self.history_container.pack(fill="both", expand=True, padx=12, pady=(0, 6), before=self.bottom_frame)
            self.toggle_history_button.configure(text="\u25BC Historique")
            target_height = self.expanded_height
        else:
            self.history_label.pack_forget()
            self.history_container.pack_forget()
            self.toggle_history_button.configure(text="\u25B2 Historique")
            target_height = self.compact_height

        self.adjust_geometry(target_height)

    def load_config(self):
        """Load plann configuration and calendars"""
        config_path = self.config_path

        print(f"\n[DEBUG] Loading config from: {config_path}")
        print(f"[DEBUG] File exists: {os.path.exists(config_path)}")

        self.section_names = []
        self.config = {}
        self.calendars = []
        self.event_calendars = []
        self.todo_calendars = []
        self._calendar_urls = set()

        try:
            config_data = read_config(config_path)

            print(f"[DEBUG] Config data loaded: {list(config_data.keys()) if config_data else 'None'}")

            # Migration: if 'default' doesn't exist but other sections do, copy the first one to 'default'
            if config_data and 'default' not in config_data:
                other_sections = [s for s in config_data.keys() if s != 'default']
                if other_sections:
                    first_section = other_sections[0]
                    print(f"[DEBUG] No 'default' section found, migrating '{first_section}' to 'default'")
                    config_data['default'] = config_data[first_section]

                    # Save the migrated config
                    try:
                        with open(config_path, 'w') as f:
                            json.dump(config_data, f, indent=4)
                        print(f"[DEBUG] Migration saved successfully")
                    except Exception as e:
                        print(f"[DEBUG] Failed to save migration: {e}")

            section_names = list(expand_config_section(config_data, self.config_section))
            if not section_names:
                self.log_message("?? Aucune section de configuration valide trouvee. Verifiez votre fichier calendar.conf.", 'error')
                self.show_config_help()
                return False

            # Resolve sections into full config dictionaries
            host_from_config = None
            model_from_config = None
            self.section_names = section_names
            for name in section_names:
                section_config = config_section(config_data, name)
                self.config[name] = section_config
                if not section_config:
                    continue
                if host_from_config is None and section_config.get('ollama_host'):
                    host_from_config = section_config['ollama_host']
                if model_from_config is None and section_config.get('ollama_model'):
                    model_from_config = section_config['ollama_model']
                calendars_for_section = find_calendars(section_config, raise_errors=False)
                if calendars_for_section:
                    self._register_calendars(calendars_for_section)

            if host_from_config:
                self.ollama_host = host_from_config
            if model_from_config:
                self.model = model_from_config

            if not self.calendars:
                self.log_message("?? Aucun calendrier trouve. Configurez plann d'abord.", 'error')
                self.show_config_help()
                return False
            else:
                self.log_message(f"\u2705 {len(self.calendars)} calendrier(s) trouve(s)", 'success')
                self.log_message(f"\u2139 Evenements: {len(self.event_calendars)} / Taches: {len(self.todo_calendars)}", 'info')
                return True

        except Exception as e:
            self.config = None
            self.calendars = []
            self.log_message(f"\u26A0 Erreur de configuration: {e}", 'error')
            self.show_config_help()
            return False

    def init_ollama(self):
        """Initialise Ollama client and parser"""
        try:
            self.ollama = OllamaClient(self.ollama_host)
            self.parser = NaturalLanguageParser(self.ollama, self.model)
            self.ollama_available = self.ollama.is_available()
        except Exception as exc:
            self.ollama = None
            self.parser = None
            self.ollama_available = False
            self.log_message(f"?? Ollama non disponible: {exc}", 'error')

    def show_config_help(self):
        """Show configuration help dialog"""
        help_message = """Plann n'est pas encore configure !

Voulez-vous ouvrir l'assistant de configuration ?

Cela vous permettra de configurer facilement
votre serveur CalDAV."""

        response = messagebox.askyesno(
            "Configuration requise",
            help_message,
            icon='question'
        )

        if response:  # User wants to configure
            self.open_config_dialog()
        else:
            # Ask if they want to quit
            if messagebox.askyesno(
                "Quitter ?",
                "Voulez-vous quitter l'application ?\n\n"
                "Sans configuration, vous ne pourrez pas ajouter d'evenements.",
                icon='warning'
            ):
                self.root.quit()
                sys.exit(0)

    def open_config_dialog(self):
        """Open configuration dialog"""
        initial_config = {}
        if self.section_names:
            initial_config = self.config.get(self.section_names[0], {})
        dialog = ConfigDialog(self.root, initial_config=initial_config, config_path=self.config_path)
        result = dialog.show()

        if result:
            # Configuration saved, reload
            self.log_message("OK configuration sauvegardee, rechargement...", 'success')
            self.config_loaded = self.load_config()
            self.init_ollama()
            self.update_ui_state()
            self.update_status()

            if self.config_loaded:
                messagebox.showinfo(
                    "Info",
                    "Configuration chargee.\nVous pouvez ajouter des evenements et taches."
                )

    def update_status(self):
        """Update Ollama connection status"""
        cfg_icon = "\u2705" if self.config_loaded else "\u26A0"
        llm_icon = "\u2705" if self.ollama_available else "\u26A0"
        status_text = ""

        if self.config_loaded and self.ollama_available:
            color = '#5cb85c'
            self.llm_icon.configure(text='[]', text_color=color)
            status_text = "pret"
        elif self.config_loaded:
            color = '#f0ad4e'
            self.llm_icon.configure(text='[]', text_color=color)
            status_text = "mode degrade"
        else:
            color = '#d9534f'
            self.llm_icon.configure(text='[]', text_color=color)
            status_text = "configuration requise"

        self.status_label.configure(text=status_text, text_color=color)

    def update_ui_state(self):
        """Update UI elements based on configuration status"""
        if not self.config_loaded:
            self.text_input.configure(state="disabled")
            self.voice_button.configure(state="disabled")
        else:
            if not self.processing:
                self.text_input.configure(state="normal")
            if self.voice_button.cget("state") != "disabled":
                self.voice_button.configure(state="normal")

        # Update status regardless
        self.update_status()

    def toggle_always_on_top(self):
        """Toggle always on top"""
        self.root.attributes('-topmost', self.always_on_top_var.get())

    def on_enter_key(self, event):
        """Handle Enter key in text input"""
        if event.state & 0x1:  # Shift+Enter: new line
            return
        else:  # Enter: add event
            self.add_event()
            return 'break'

    def add_event(self):
        """Add event/task from text input"""
        text = self.text_input.get("1.0", "end").strip()

        if not text:
            return

        if self.processing:
            return

        if not self.ollama_available:
            messagebox.showerror(
                "Ollama non disponible",
                "Ollama n'est pas accessible. Assurez-vous qu'il est en cours d'execution:\n\n"
                "ollama serve"
            )
            return

        if not self.calendars:
            messagebox.showerror(
                "Aucun calendrier",
                "Aucun calendrier trouve.\n\n"
                "Configurez plann d'abord avec: plann --help"
            )
            return

        # Lock input during processing
        self.processing = True
        self.text_input.configure(state="disabled")
        self.status_label.configure(text="envoi en cours", text_color="#0a84ff")

        # Process in background thread
        threading.Thread(target=self._process_event, args=(text,), daemon=True).start()

    def _process_event(self, text):
        """Process event in background thread"""
        success = False
        try:
            # Log input
            self.log_message(f"\U0001F4DD Entree: {text}", 'info')

            # Parse with Ollama
            parsed = self.parser.parse_event(text)

            # Format for plann
            command_name, timespec, summary, kwargs = format_for_plann(parsed)

            # Create a mock context object for plann functions
            class MockContext:
                def __init__(self, calendars):
                    self.obj = {
                        'calendars': calendars,
                        'ical_fragment': ''
                    }

            # Execute
            if kwargs.get('todo'):
                # Prepare kwargs for _add_todo
                target_calendars = self.todo_calendars or self.calendars
                if not target_calendars:
                    self.log_message("\u26A0 Aucun calendrier compatible TODO", 'error')
                    return

                ctx = MockContext(target_calendars)

                todo_kwargs = {'summary': (summary,)}
                if kwargs.get('set_due'):
                    todo_kwargs['set_due'] = kwargs['set_due']
                if kwargs.get('set_priority'):
                    todo_kwargs['set_priority'] = kwargs['set_priority']
                if kwargs.get('set_alarm'):
                    todo_kwargs['set_alarm'] = kwargs['set_alarm']

                _add_todo(ctx, **todo_kwargs)
                event_icon = "\u2705"

            elif kwargs.get('event'):
                # Prepare kwargs for _add_event
                target_calendars = self.event_calendars or self.calendars
                if not target_calendars:
                    self.log_message("\u26A0 Aucun calendrier compatible evenements", 'error')
                    return

                ctx = MockContext(target_calendars)

                event_kwargs = {'summary': summary}
                if kwargs.get('alarm'):
                    event_kwargs['alarm'] = kwargs['alarm']
                if kwargs.get('set_location'):
                    event_kwargs['set_location'] = kwargs['set_location']

                _add_event(ctx, timespec, **event_kwargs)
                event_icon = "\U0001F4C5"

            else:
                self.log_message("\u26A0 Type de commande non gere", 'error')
                return

            # Log success
            self.log_message(f"{event_icon} Ajoute: {summary}", 'success')
            self.status_label.configure(text="operation terminee", text_color="#5cb85c")
            success = True
            self.root.after(0, lambda: self._unlock_input(clear=True))

        except Exception as e:
            self.log_message(f"\u274C Erreur: {str(e)}", 'error')
            self.status_label.configure(text="erreur", text_color="#d9534f")

        finally:
            if not success:
                self.root.after(0, lambda: self._unlock_input(clear=False))

    def _unlock_input(self, clear):
        """Reset input area after processing"""
        self.processing = False
        self.text_input.configure(state="normal")
        if clear:
            self.text_input.delete("1.0", "end")
        self.text_input.focus_set()

    def voice_input(self):
        """Voice input mode"""
        try:
            import speech_recognition as sr
        except ImportError:
            messagebox.showerror(
                "Module manquant",
                "Le module 'speech_recognition' n'est pas installe.\n\n"
                "Installez-le avec:\n"
                "pip install SpeechRecognition pyaudio"
            )
            return

        # Disable button
        self.voice_button.configure(state="disabled", text="\u231B")

        # Process in background
        threading.Thread(target=self._voice_input_thread, daemon=True).start()

    def _voice_input_thread(self):
        """Voice input in background thread"""
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()

            with sr.Microphone() as source:
                self.log_message("\U0001F3A4 Calibration...", 'info')
                recognizer.adjust_for_ambient_noise(source, duration=1)

                self.log_message("\U0001F3A4 Parlez maintenant...", 'info')
                audio = recognizer.listen(source, timeout=15, phrase_time_limit=25)

            self.log_message("\U0001F3A4 Transcription...", 'info')

            try:
                text = recognizer.recognize_google(audio, language='fr-FR')
                self.log_message(f"\U0001F3A4 Capture: {text}", 'success')

                # Set text in input
                self.root.after(0, lambda: self.text_input.insert("1.0", text))

                # Auto-add
                self.root.after(500, self.add_event)

            except sr.UnknownValueError:
                self.log_message("\u274C Impossible de comprendre l'audio", 'error')
            except sr.RequestError as e:
                self.log_message(f"\u274C Erreur du service: {e}", 'error')

        except Exception as e:
            self.log_message(f"\u274C Erreur vocale: {str(e)}", 'error')

        finally:
            self.root.after(0, lambda: self.voice_button.configure(state="normal", text="\U0001F3A4 Dicter"))

    def log_message(self, message, tag='info'):
        """Log message to history"""
        def _log():
            self.history_text.configure(state="normal")

            # Add timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.history_text.insert("end", f"[{timestamp}] ", 'time')
            self.history_text.insert("end", f"{message}\n", tag)

            # Auto-scroll to bottom
            self.history_text.see("end")

            self.history_text.configure(state="disabled")

        self.root.after(0, _log)

    def clear_history(self):
        """Clear history text"""
        self.history_text.configure(state="normal")
        self.history_text.delete("1.0", "end")
        self.history_text.configure(state="disabled")

    def run(self):
        """Run the GUI"""
        self.root.mainloop()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Minimal GUI for plann with Ollama")

    parser.add_argument(
        '--model',
        default=os.environ.get('OLLAMA_MODEL', 'llama2'),
        help="Modele Ollama a utiliser (defaut: llama2)"
    )

    parser.add_argument(
        '--ollama-host',
        default=os.environ.get('OLLAMA_HOST', 'http://localhost:11434'),
        help="URL de l'API Ollama (defaut: http://localhost:11434)"
    )

    parser.add_argument(
        '--config-section',
        default='default',
        help="Section de configuration a utiliser (defaut: default)"
    )

    args = parser.parse_args()

    # Create and run GUI
    app = PlannGUI(
        config_section=args.config_section,
        model=args.model,
        ollama_host=args.ollama_host
    )
    app.run()


if __name__ == '__main__':
    main()

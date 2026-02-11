import flet as ft
import ollama
import speech_recognition as sr
import pygame
import threading
import os
import subprocess
from duckduckgo_search import DDGS

# --- CONFIGURATION ---
DEFAULT_MODEL = "llama3.2"
DEFAULT_VOICE = "en-US-AriaNeural"

# Global Variables
current_model = DEFAULT_MODEL
current_voice = DEFAULT_VOICE
stop_audio_flag = False
is_muted = False  # Track mute state

# --- AUDIO FUNCTIONS ---
def play_audio(file_path):
    global stop_audio_flag, is_muted
    if is_muted: return # Don't play if muted
    
    try:
        pygame.mixer.init()
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            if stop_audio_flag:
                pygame.mixer.music.stop()
                break
            pygame.time.Clock().tick(10)
        pygame.mixer.quit()
        if os.path.exists(file_path):
            os.remove(file_path)
    except Exception as e:
        print(f"Audio Error: {e}")

def generate_voice(text, voice):
    output_file = "voice_reply.mp3"
    safe_text = text.replace('"', '').replace("'", "")
    command = f'edge-tts --voice {voice} --text "{safe_text}" --write-media {output_file}'
    subprocess.run(command, shell=True)
    return output_file

def speak_thread(text, voice, page_update_callback):
    global stop_audio_flag
    stop_audio_flag = False
    try:
        audio_file = generate_voice(text, voice)
        play_audio(audio_file)
    except Exception:
        pass
    page_update_callback()

# --- MAIN APP ---
def main(page: ft.Page):
    # 1. Page Config
    page.title = "Sora AI"
    page.theme_mode = ft.ThemeMode.DARK
    page.window_width = 450
    page.window_height = 800
    page.padding = 0
    page.bgcolor = ft.Colors.BLACK
    
    convo_history = []

    # --- UI ELEMENTS ---

    # Status Text (Moved to be used later)
    status_indicator = ft.Text("Ready", size=12, color=ft.Colors.GREY_500, italic=True)

    # Chat List
    chat_list = ft.ListView(
        expand=True,
        spacing=12,
        padding=20,
        auto_scroll=True,
    )

    # --- ACTION HANDLERS ---
    
    def open_drawer_click(e):
        # FIX: Force open by setting property directly
        page.drawer.open = True
        page.update()

    def close_drawer(e=None):
        page.drawer.open = False
        page.update()

    def toggle_audio(e):
        global is_muted
        is_muted = not is_muted
        
        # Visual Update
        if is_muted:
            audio_btn.icon = ft.Icons.VOLUME_OFF
            audio_btn.icon_color = ft.Colors.RED_400
            page.snack_bar = ft.SnackBar(ft.Text("Voice Muted 🔇"))
        else:
            audio_btn.icon = ft.Icons.VOLUME_UP
            audio_btn.icon_color = ft.Colors.GREEN_400
            page.snack_bar = ft.SnackBar(ft.Text("Voice Enabled 🔊"))
            
        page.snack_bar.open = True
        page.update()

    def change_model(e):
        global current_model
        current_model = e.control.value
        page.snack_bar = ft.SnackBar(ft.Text(f"Model: {current_model}"))
        page.snack_bar.open = True
        close_drawer()
        page.update()

    def change_voice(e):
        global current_voice
        current_voice = e.control.value
        page.snack_bar = ft.SnackBar(ft.Text(f"Voice Changed"))
        page.snack_bar.open = True
        close_drawer()
        page.update()

    def clear_chat(e):
        chat_list.controls.clear()
        convo_history.clear()
        close_drawer()
        page.update()

    # --- DRAWER SETUP ---
    # Fix: Define dropdowns without on_change first
    model_dd = ft.Dropdown(
        value=DEFAULT_MODEL,
        options=[ft.dropdown.Option("llama3.2"), ft.dropdown.Option("mistral")],
        border_color=ft.Colors.BLUE_600,
        text_size=14,
    )
    model_dd.on_change = change_model

    voice_dd = ft.Dropdown(
        value=DEFAULT_VOICE,
        options=[
            ft.dropdown.Option("en-US-AriaNeural", "Female (US)"),
            ft.dropdown.Option("en-US-ChristopherNeural", "Male (US)"),
            ft.dropdown.Option("en-GB-SoniaNeural", "Female (UK)"),
        ],
        border_color=ft.Colors.BLUE_600,
        text_size=14,
    )
    voice_dd.on_change = change_voice

    my_drawer = ft.NavigationDrawer(
        controls=[
            ft.Container(height=20),
            ft.Text("Settings", size=24, weight="bold", text_align="center", color=ft.Colors.WHITE),
            ft.Divider(color=ft.Colors.GREY_800),
            ft.Container(
                content=ft.Column([
                    ft.Text("AI Model", color=ft.Colors.GREY_400),
                    model_dd,
                    ft.Container(height=10),
                    ft.Text("Voice", color=ft.Colors.GREY_400),
                    voice_dd,
                    ft.Container(height=20),
                    ft.ElevatedButton(
                        "Clear History", 
                        icon=ft.Icons.DELETE, 
                        color=ft.Colors.WHITE,
                        bgcolor=ft.Colors.RED_700,
                        width=200,
                        on_click=clear_chat
                    )
                ]),
                padding=20
            )
        ],
        bgcolor=ft.Colors.GREY_900,
    )
    
    page.drawer = my_drawer

    # --- CHAT LOGIC ---
    def add_message(text, sender="user"):
        is_user = sender == "user"
        align = ft.MainAxisAlignment.END if is_user else ft.MainAxisAlignment.START
        
        bg_color = ft.Colors.BLUE_900 if is_user else ft.Colors.GREY_800
        
        # Markdown for AI, Text for User
        content = ft.Markdown(
            text, 
            selectable=True, 
            extension_set="github",
            code_theme="atom-one-dark"
        ) if not is_user else ft.Text(text, color=ft.Colors.WHITE)

        # FIX: Removed 'constraints' causing crash. Using 'width' instead.
        bubble = ft.Container(
            content=content,
            padding=15,
            border_radius=ft.border_radius.only(
                top_left=15, top_right=15, 
                bottom_left=15 if is_user else 5, 
                bottom_right=5 if is_user else 15
            ),
            bgcolor=bg_color,
            # If user, let it auto-size. If AI, give it fixed width so code blocks look good.
            width=None if is_user else 320, 
        )
        
        chat_list.controls.append(ft.Row([bubble], alignment=align))
        page.update()
        return content

    def process_ai_response(user_input):
        status_indicator.value = "Thinking..."
        status_indicator.color = ft.Colors.BLUE_400
        page.update()

        convo_history.append({'role': 'user', 'content': user_input})
        
        messages = [
            {'role': 'system', 'content': f"You are Sora. Helpful, friendly, female assistant."}
        ] + convo_history[-5:]

        ai_bubble = add_message("...", sender="ai")
        full_resp = ""

        try:
            if any(x in user_input.lower() for x in ["search", "news", "weather"]):
                status_indicator.value = "Searching..."
                page.update()
                results = DDGS().text(user_input, max_results=1)
                if results:
                    messages[-1]['content'] += f"\n[Context: {results[0]['body']}]"

            status_indicator.value = "Typing..."
            page.update()

            stream = ollama.chat(model=current_model, messages=messages, stream=True)
            for chunk in stream:
                content = chunk['message']['content']
                full_resp += content
                ai_bubble.value = full_resp
                ai_bubble.update()

            final_text = full_resp.replace("<think>", "").replace("</think>", "")
            ai_bubble.value = final_text
            ai_bubble.update()
            
            convo_history.append({'role': 'assistant', 'content': final_text})
            
            status_indicator.value = "Speaking..."
            status_indicator.color = ft.Colors.PINK_400
            page.update()
            
            threading.Thread(target=speak_thread, args=(final_text, current_voice, lambda: reset_status())).start()

        except Exception as e:
            ai_bubble.value = f"Error: {e}"
            ai_bubble.update()
            reset_status()

    def reset_status():
        status_indicator.value = "Ready"
        status_indicator.color = ft.Colors.GREY_500
        page.update()

    def on_send(e):
        if text_input.value:
            txt = text_input.value
            text_input.value = ""
            add_message(txt, sender="user")
            threading.Thread(target=process_ai_response, args=(txt,)).start()

    def on_mic(e):
        status_indicator.value = "Listening..."
        status_indicator.color = ft.Colors.RED_400
        page.update()
        threading.Thread(target=listen_logic).start()

    def listen_logic():
        r = sr.Recognizer()
        with sr.Microphone() as source:
            try:
                r.adjust_for_ambient_noise(source)
                audio = r.listen(source, timeout=5)
                text = r.recognize_google(audio).lower()
                text_input.value = text
                page.update()
                on_send(None)
            except:
                reset_status()

    # --- LAYOUT ASSEMBLY ---
    
    # 1. AppBar - Sound Button uses toggle logic now
    audio_btn = ft.IconButton(
        ft.Icons.VOLUME_UP, 
        icon_color=ft.Colors.GREEN_400, 
        on_click=toggle_audio, 
        tooltip="Toggle Voice"
    )

    app_bar = ft.Container(
        content=ft.Row([
            ft.IconButton(ft.Icons.MENU, icon_color=ft.Colors.WHITE, on_click=open_drawer_click),
            ft.Text("Sora AI", size=20, weight="bold", color=ft.Colors.WHITE),
            audio_btn
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=ft.padding.symmetric(horizontal=10, vertical=10),
        bgcolor=ft.Colors.GREY_900
    )

    # 2. Input Area
    text_input = ft.TextField(
        hint_text="Type a message...",
        hint_style=ft.TextStyle(color=ft.Colors.GREY_600),
        border_color="transparent",
        bgcolor="transparent",
        color=ft.Colors.WHITE,
        expand=True,
        on_submit=on_send,
        text_size=16
    )

    input_bar = ft.Container(
        content=ft.Row([
            text_input,
            ft.IconButton(ft.Icons.MIC, icon_color=ft.Colors.PINK_500, on_click=on_mic),
            ft.IconButton(ft.Icons.SEND_ROUNDED, icon_color=ft.Colors.BLUE_500, on_click=on_send),
        ]),
        bgcolor=ft.Colors.GREY_900,
        border_radius=30,
        padding=ft.padding.symmetric(horizontal=15, vertical=5),
        # FIX: Padding to align with status text
        margin=ft.padding.only(left=10, right=10, bottom=10) 
    )

    # 3. Bottom Assembly (Status + Input)
    # FIX: Status text aligned with input
    bottom_area = ft.Container(
        content=ft.Column([
            ft.Container(content=status_indicator, padding=ft.padding.only(left=30)), 
            input_bar
        ], spacing=5),
        bgcolor=ft.Colors.BLACK
    )

    page.add(
        ft.Column([
            app_bar,
            chat_list,
            bottom_area
        ], expand=True, spacing=0)
    )

ft.app(target=main)
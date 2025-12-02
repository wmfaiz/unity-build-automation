import glob
import os, shutil
import plistlib
import random
import socket
import sys, re
import hashlib
import json
import platform
import stat
import traceback
import urllib
from time import sleep
from warnings import catch_warnings

import httplib2
import psutil
import tkinter as tk
import requests
import base64
import subprocess, time
import tempfile
import servo
import certifi
import urllib3
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, quote_plus
from cryptography.fernet import Fernet
from google.oauth2 import service_account
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from requests.adapters import HTTPAdapter
from yarg.client import session

for dirpath, dirnames, filenames in os.walk('.'):
    for dirname in dirnames:
        if dirname == '__pycache__':
            shutil.rmtree(os.path.join(dirpath, dirname), ignore_errors=True)

project_settings_asset = "ProjectSettings/ProjectSettings.asset"
editor_settings_asset = "ProjectSettings/EditorSettings.asset"
env_index_map = {
    "QA_ENV": 0,
    "PRODUCTION_ENV": 1,
    "STAGING_ENV": 2,
    "DEVELOP_ENV": 3
}
env_name_map = {
    "QA_ENV": "7c9b7696-78b1-41a8-9143-9b86f0519e10",
    "PRODUCTION_ENV": "c5df4fe6-91f6-48dd-b0fe-9f0f78b33384",
    "STAGING_ENV": "c8bdd6b3-a88c-4cef-a261-6d4376d91c9e",
    "DEVELOP_ENV": "edea636c-6f6f-44e0-a63b-6f78379c6f78",
}
bucket_name_map = {
    "QA_ENV": "5d5e31cb-3b6e-4bb8-8af3-df215b983453",
    "PRODUCTION_ENV": "d1b05e98-2ef0-461c-a391-94577c836dd3",
    "STAGING_ENV": "507c0977-7147-4ec0-9f53-5033cec78985",
    "DEVELOP_ENV": "654d06bb-54ff-4a6e-b2c3-6914d3fceb4f",
}
bucket_token_map = {
    "QA_ENV": "3700a83fe91bbf1ffee46aa6cf27d96e",
    "PRODUCTION_ENV": "f8bbb34a820cb3537a4ddedbac8c8b75",
    "STAGING_ENV": "f7058bad8a5bc460a0f57db7229aad61",
    "DEVELOP_ENV": "7793ee305abb7dc3a3f0c93bc6529980",
}
env_shorthand_name_map = {
    "QA_ENV": "qa",
    "PRODUCTION_ENV": "production",
    "STAGING_ENV": "staging",
    "DEVELOP_ENV": "dev",
}
ccd_environment_map = {
    "QA_ENV": "qa",
    "PRODUCTION_ENV": "production",
    "STAGING_ENV": "staging",
    "DEVELOP_ENV": "develop",
}
env_longhand_name_map = {
    "qa": "QA_ENV",
    "production": "PRODUCTION_ENV",
    "staging": "STAGING_ENV",
    "dev": "DEVELOP_ENV",
    "develop": "DEVELOP_ENV"
}
package_map = {
    "dev": "jp.okakichi.heroes.dev",
    "qa": "jp.okakichi.heroes.qa",
    "staging": "jp.okakichi.heroes.staging",
    "production": "jp.okakichi.heroes",
}

script_dir = os.path.dirname(os.path.abspath(__file__))

def write_to_console(fromwho, process=None, text_widget=None, success_msg=None, failure_msg=None):
    prefix = f"{fromwho}: " if fromwho else ""
    if process and hasattr(process.stdout, 'readline'):
        for line in iter(process.stdout.readline, ''):
            line_text = prefix + line
            text_widget.configure(state='normal')
            text_widget.insert(tk.END, line_text)
            text_widget.see(tk.END)
            text_widget.configure(state='disabled')
        process.stdout.close()
        process.wait()
    elif process and hasattr(process.stdout, 'splitlines'):
        for line in process.stdout.splitlines():
            line_text = prefix + line + "\n"
            text_widget.configure(state='normal')
            text_widget.insert(tk.END, line_text)
            text_widget.see(tk.END)
            text_widget.configure(state='disabled')
    status_msg = ""
    if process is None and success_msg:
        status_msg = success_msg
    elif process is not None:
        if hasattr(process, 'returncode'):
            if process.returncode == 0 and success_msg:
                status_msg = success_msg
            elif process.returncode != 0 and failure_msg:
                status_msg = failure_msg
    if status_msg:
        text_widget.configure(state='normal')
        text_widget.insert(tk.END, prefix + status_msg + "\n")
        text_widget.see(tk.END)
        text_widget.configure(state='disabled')
    
def clear_console_log(text_widget):
    text_widget.configure(state='normal')
    text_widget.delete('1.0', tk.END)
    text_widget.configure(state='disabled')

def is_unity_editor_running(project_path=None):
    current_os = platform.system()
    target_names = ["Unity.exe"] if current_os == "Windows" else ["Unity"]
    normalized_project_path = (
        os.path.abspath(project_path).replace("\\", "/").lower()
        if project_path else None
    )
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            name = proc.info['name']
            cmdline = " ".join(proc.info.get('cmdline') or []).replace("\\", "/").lower()
            if name not in target_names:
                continue
            if any(hub in cmdline for hub in ["unityhub", "unity hub"]):
                continue
            if not normalized_project_path:
                return True
            if normalized_project_path in cmdline:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False

def send_editor_command(method_name: str, project_path: str):
    editor_cmd_dir = os.path.join(project_path, "EditorCommands")
    os.makedirs(editor_cmd_dir, exist_ok=True)
    cmd_file = os.path.join(editor_cmd_dir, f"{method_name}.cmd")
    if not os.path.exists(cmd_file):
        with open(cmd_file, "w") as f:
            f.write("run")

def restore_widget_text_to_normal(text_widget, exception):
    text_widget.configure(state='normal')
    text_widget.insert(tk.END, f"Error {exception}")
    text_widget.configure(state='disabled')

def remote_public_build(text_widget, build_time_history, unity_path, project_path, env_id,
                                version, note, push_to_cloud, cloud_api_key, orgs_id, project_id,
                                env_bucket_id_payload, player_prefs, led):
    try:
        version_code =  get_version_code(env_id, text_widget)
        log_dir = os.path.join(project_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        build_args = [
                unity_path,
                "-batchmode",
                "-quit",
                "-projectPath", project_path,
                "-executeMethod", "ScriptingBuilderHelpers.RemoteAndroidPublicBuild",
                "--value1", env_id,
                "--value2", version_code,
                "--value3", version,
                "--value4", note,
                "--value5", push_to_cloud,
                "--value6", cloud_api_key,
                "--value7", orgs_id,
                "--value8", project_id,
                "--value9", env_bucket_id_payload,
                "--value10", platform.system(),
                "--value11", json.dumps(player_prefs),
                "--value13", env_shorthand_name_map[env_id]
        ]
        set_or_replace_arg(build_args, "--value12", "Android")
        android_build = build_args + ["-buildTarget", "Android", "-logFile", "-"]
        write_to_console("Start Android Build",None, text_widget)
        ret_android, output = safeguard_launcher(
            "[PUBLIC] Android Build", android_build, text_widget, project_path,
            led, build_time_history,
            success_msg="[SUCCESS] Android build",
            failure_msg="[FAILED] Android build failed. Check logs/android_build.log"
        )
        publish_android(text_widget, env_id, version_code, version, note)
            
        set_or_replace_arg(build_args, "--value12", "iOS")
        ios_build = build_args + ["-buildTarget", "iOS", "-logFile", "-"]
        write_to_console("Start iOS Build",None, text_widget)
        ret_ios, output = safeguard_launcher(
            "[PUBLIC] iOS Build", ios_build, text_widget, project_path,
            led, build_time_history,
            success_msg="[SUCCESS] iOS build",
            failure_msg="[FAILED] iOS build failed. Check logs/ios_build.log"
        )
        publish_ios(text_widget, env_id, version, note)
    except Exception as e:
        print(f"[EXCEPTION] {e}")
        traceback.print_exc()
        restore_widget_text_to_normal(text_widget, e)


def remote_public_build_android(text_widget, build_time_history, unity_path, project_path, env_id,
                        version, note, push_to_cloud, cloud_api_key, orgs_id, project_id,
                        env_bucket_id_payload, player_prefs, led, upload=True):
    try:
        version_code = get_version_code(env_id, text_widget)
        log_dir = os.path.join(project_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        build_args = [
            unity_path,
            "-batchmode",
            "-quit",
            "-projectPath", project_path,
            "-executeMethod", "ScriptingBuilderHelpers.RemoteAndroidPublicBuild",
            "--value1", env_id,
            "--value2", version_code,
            "--value3", version,
            "--value4", note,
            "--value5", push_to_cloud,
            "--value6", cloud_api_key,
            "--value7", orgs_id,
            "--value8", project_id,
            "--value9", env_bucket_id_payload,
            "--value10", platform.system(),
            "--value11", json.dumps(player_prefs),
            "--value12", "Android",
            "--value13", env_shorthand_name_map[env_id]
        ]
        android_build = build_args + ["-buildTarget", "Android", "-logFile", "-"]
        write_to_console("Start Android Build",None, text_widget)
        ret_android, output = safeguard_launcher(
            "[PUBLIC] Android Build", android_build, text_widget, project_path,
            led, build_time_history,
            success_msg="[SUCCESS] Android build",
            failure_msg="[FAILED] Android build failed. Check logs/android_build.log"
        )
        if upload:
            publish_android(text_widget, env_id, version_code, version, note)
    except Exception as e:
        servo.build_log(str(e))
        traceback.print_exc()
        restore_widget_text_to_normal(text_widget, e)

def remote_public_build_ios(text_widget, build_time_history, unity_path, project_path, env_id,
                                version, note, push_to_cloud, cloud_api_key, orgs_id, project_id,
                                env_bucket_id_payload, player_prefs, led, upload=True):
    try:
        version_code = get_version_code(env_id, text_widget)
        log_dir = os.path.join(project_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        build_args = [
            unity_path,
            "-batchmode",
            "-quit",
            "-projectPath", project_path,
            "-executeMethod", "ScriptingBuilderHelpers.RemoteAndroidPublicBuild",
            "--value1", env_id,
            "--value2", version_code,
            "--value3", version,
            "--value4", note,
            "--value5", push_to_cloud,
            "--value6", cloud_api_key,
            "--value7", orgs_id,
            "--value8", project_id,
            "--value9", env_bucket_id_payload,
            "--value10", platform.system(),
            "--value11", json.dumps(player_prefs),
            "--value12", "iOS",
            "--value13", env_shorthand_name_map[env_id]
        ]
        ios_build = build_args + ["-buildTarget", "iOS", "-logFile", "-"]
        write_to_console("Start iOS Build",None, text_widget)
        ret_ios, output = safeguard_launcher(
            "[PUBLIC] iOS Build", ios_build, text_widget, project_path,
            led, build_time_history,
            success_msg="[SUCCESS] iOS build",
            failure_msg="[FAILED] iOS build failed. Check logs/ios_build.log"
        )
        if upload:
            publish_ios(text_widget, env_id, version, note)
    except Exception as e:
        servo.build_log(str(e))
        traceback.print_exc()
        restore_widget_text_to_normal(text_widget, e)


def remote_test_build(text_widget, build_time_history, unity_path, project_path, env_id,
                              version, note, push_to_cloud, cloud_api_key, orgs_id, project_id,
                              env_bucket_id_payload, player_prefs, led):
    try:
        log_dir = os.path.join(project_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        build_args = [
            unity_path,
            "-batchmode",
            "-quit",
            "-projectPath", project_path,
            "-executeMethod", "ScriptingBuilderHelpers.RemoteAndroidTestBuild",
            "--value1", env_id,
            "--value2", version,
            "--value3", note,
            "--value4", push_to_cloud,
            "--value5", cloud_api_key,
            "--value6", orgs_id,
            "--value7", project_id,
            "--value8", env_bucket_id_payload,
            "--value9", platform.system(),
            "--value10", json.dumps(player_prefs),
            "--value12", env_shorthand_name_map[env_id]
        ]
        set_or_replace_arg(build_args, "--value11", "Android")
        android_build = build_args + ["-buildTarget", "Android", "-logFile", "-"]
        write_to_console("Start Android Build",None, text_widget)
        ret_android, output = safeguard_launcher(
            "[TEST] Android Build", android_build, text_widget, project_path,
            led, build_time_history,
            success_msg="[SUCCESS] Android build",
            failure_msg="[FAILED] Android build failed. Check logs/android_build.log"
        )

        set_or_replace_arg(build_args, "--value11", "iOS")
        ios_build = build_args + ["-buildTarget", "iOS", "-logFile", "-"]
        write_to_console("Start iOS Build",None, text_widget)
        
        ret_ios, output = safeguard_launcher(
            "[TEST] iOS Build", ios_build, text_widget, project_path,
            led, build_time_history,
            success_msg="[SUCCESS] iOS build",
            failure_msg="[FAILED] iOS build failed. Check logs/ios_build.log"
        )
    except Exception as e:
        restore_widget_text_to_normal(text_widget,e)


def remote_both_build(text_widget, build_time_history, unity_path, project_path, env_id,
                              version, note, push_to_cloud, cloud_api_key, orgs_id, project_id,
                              env_bucket_id_payload, player_prefs, led):
    try:
        if is_unity_editor_running(project_path):
            send_editor_command("RemoteAndroidBothBuild", project_path)
        else:
            log_dir = os.path.join(project_path, "logs")
            os.makedirs(log_dir, exist_ok=True)
            build_args = [
                unity_path,
                "-batchmode",
                "-quit",
                "-projectPath", project_path,
                "-executeMethod", "ScriptingBuilderHelpers.RemoteAndroidBothBuild",
                "--value1", env_id,
                "--value2", version,
                "--value3", note,
                "--value4", push_to_cloud,
                "--value5", cloud_api_key,
                "--value6", orgs_id,
                "--value7", project_id,
                "--value8", env_bucket_id_payload,
                "--value9", platform.system(),
                "--value10", json.dumps(player_prefs),
                "--value13", env_shorthand_name_map[env_id]
            ]
            set_or_replace_arg(build_args, "--value11", "apk")
            set_or_replace_arg(build_args, "--value12", "Android")
            android_build = build_args + ["-buildTarget", "Android", "-logFile", "-"]
            write_to_console("Start Android Build",None, text_widget)
            ret_apk_android, output = safeguard_launcher(
                "[BOTH] Android Build", android_build, text_widget, project_path,
                led, build_time_history,
                success_msg="[SUCCESS] Android build",
                failure_msg="[FAILED] Android build failed."
            )

            set_or_replace_arg(build_args, "--value11", "aab")
            set_or_replace_arg(build_args, "--value12", "Android")
            android_build = build_args + ["-buildTarget", "Android", "-logFile", "-"]
            write_to_console("Start Android Build",None, text_widget)
            ret_aab_android, output = safeguard_launcher(
                "[BOTH] Android Build", android_build, text_widget, project_path,
                led, build_time_history,
                success_msg="[SUCCESS] Android build",
                failure_msg="[FAILED] Android build failed."
            )

            set_or_replace_arg(build_args, "--value11", "iOS")
            ios_build = build_args + ["-buildTarget", "iOS", "-logFile", "-"]
            write_to_console("Start iOS Build",None, text_widget)
            ret_ios, output = safeguard_launcher(
                "[BOTH] iOS Build", ios_build, text_widget, project_path,
                led, build_time_history,
                success_msg="[SUCCESS] iOS build",
                failure_msg="[FAILED] iOS build failed."
            )
    except Exception as e:
        restore_widget_text_to_normal(text_widget,e)


def remote_change_environment(text_widget, build_time_history, unity_path, project_path, player_prefs, selected, led):
    try:
        build_args = [
            unity_path,
            "-batchmode",
            "-quit",
            "-projectPath", project_path,
            "-executeMethod", "ScriptingBuilderHelpers.SwitchEnvironment",
            "--value1", selected,
            "--value2", script_dir,
            "--value3", json.dumps(player_prefs),
            "-logFile", "-"
        ]
        write_to_console("Start Change Environment", None, text_widget)
        ret, output = safeguard_launcher(
            "Change environment", build_args, text_widget, project_path,
            led, build_time_history,
            success_msg="[SUCCESS] Change environment success",
            failure_msg="[FAILED] Change environment failed."
        )
        write_environment(selected)
    except Exception as e:
        servo.build_log(str(e))
        restore_widget_text_to_normal(text_widget, e)

def run_get_current_environment(unity_path, project_path, text_widget, build_time_history, env, led=None):
    try:
        build_args = [
            unity_path,
            "-batchmode",
            "-quit",
            "-projectPath", project_path,
            "-executeMethod", "ScriptingBuilderHelpers.RemoteGetEnvironment",
            "-logFile", "-"
        ]
        write_to_console("Confirming environment", None, text_widget)
        ret, output = safeguard_launcher(
            "Confirming environment", build_args, text_widget, project_path,
            led, build_time_history,
            success_msg="[SUCCESS] Confirming environment success",
            failure_msg="[FAILED] Confirming environment failed."
        )
        for line in output:
            if f"[ENV] {env.upper()}" in line:
                write_to_console(f"[INFO] Detected environment from Unity logs: {line.strip()}", None, text_widget)
                return 1
        write_to_console(f"[WARNING] Expected environment '{env}' not found in logs.", None, text_widget)
        return 0
    except Exception as e:
        write_to_console(f"[ERROR] run_get_current_environment exception: {str(e)}", None, text_widget)
        return 0

def build_addressable_android(text_widget, build_time_history, unity_path, project_path, version, ccd_path, env_id, project_id, bucket_id, led):
    try:
        log_dir = os.path.join(project_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        env_name = env_name_map[env_id]
        BASE_ARGS = [
            unity_path,
            "-batchmode",
            "-quit",
            "-projectPath", project_path,
            "-executeMethod", "ScriptingBuilderHelpers.BuildAddressable",
            "--value1", env_name,
            "--value2", project_id,
            "--value3", bucket_id,
            "--value4", "Android",
            "--value5", version,
            "-logFile", "-"
        ]
        write_to_console("Start Android Addressables",None, text_widget)
        ret_android, output = safeguard_launcher(
            "Android Addressables", BASE_ARGS, text_widget, project_path,
            led, build_time_history,
            success_msg="[SUCCESS] Android Addressables build",
            failure_msg="[FAILED] Android Addressables build failed. Check logs/android_addressable.log"
        )
        prepare_and_patch_addressable(env_id, version, ccd_path, "Android")
    except Exception as e:
        servo.build_log(str(e))
        restore_widget_text_to_normal(text_widget,e)

def build_addressable_ios(text_widget, build_time_history, unity_path, project_path, version, ccd_path, env_id, project_id, bucket_id, led):
    try:
        log_dir = os.path.join(project_path, "logs")
        os.makedirs(log_dir, exist_ok=True)
        env_name = env_name_map[env_id]
        BASE_ARGS = [
            unity_path,
            "-batchmode",
            "-quit",
            "-projectPath", project_path,
            "-executeMethod", "ScriptingBuilderHelpers.BuildAddressable",
            "--value1", env_name,
            "--value2", project_id,
            "--value3", bucket_id,
            "--value4", "iOS",
            "--value5", version,
            "-logFile", "-"
        ]
        write_to_console("Start iOS Addressables",None, text_widget)
        ret_ios, output = safeguard_launcher(
            "iOS Addressables", BASE_ARGS, text_widget, project_path,
            led, build_time_history,
            success_msg="[SUCCESS] iOS Addressables build",
            failure_msg="[FAILED] iOS Addressables build failed. Check logs/ios_addressable.log"
        )
        prepare_and_patch_addressable(env_id, version, ccd_path, "iOS")
    except Exception as e:
        servo.build_log(str(e))
        restore_widget_text_to_normal(text_widget,e)
    
#Work In Progress
def patching_addressable(text_widget, build_time_history, unity_path, project_path, env_id, led):
    BASE_ARGS = [
        unity_path,
        "-batchmode",
        "-quit",
        "-projectPath", project_path,
        "-executeMethod", "ScriptingBuilderHelpers.PatchAddressable",
        "--value1", env_id,
        "--value2", platform.system(),
    ]
    set_or_replace_arg(BASE_ARGS, "--value3", "Android")
    android_cmd = BASE_ARGS + ["-buildTarget", "Android", "-logFile", "-"]
    write_to_console("Start patching Android Addressables",None, text_widget)
    ret_android, output = safeguard_launcher(
        "Patching Android", android_cmd, text_widget, project_path,
        led, build_time_history,
        success_msg="[SUCCESS] Patching Android Addressables build",
        failure_msg="[FAILED] Patching Android Addressables build failed"
    )

    set_or_replace_arg(BASE_ARGS, "--value3", "iOS")
    ios_cmd = BASE_ARGS + ["-buildTarget", "iOS", "-logFile", "-"]
    write_to_console("Start patching iOS Addressables",None, text_widget)
    ret_ios, output = safeguard_launcher(
        "Patching iOS", ios_cmd, text_widget, project_path,
        led, build_time_history,
        success_msg="[SUCCESS] Patching iOS Addressables build",
        failure_msg="[FAILED] Patching iOS Addressables build failed"
    )
    
def android_gradle_resolver(text_widget, build_time_history, unity_path, project_path, led):
    build_args = [
        unity_path,
        "-batchmode",
        "-quit",
        "-projectPath", project_path,
        "-executeMethod", "ScriptingBuilderHelpers.AndroidResolver",
        "-logFile", "-"
    ]
    ret_rebuild, output = safeguard_launcher(
        "Force resolve gradle", build_args, text_widget, project_path,
        led, build_time_history,
        success_msg="[SUCCESS] Force resolve gradle",
        failure_msg="[FAILED] Force resolve gradle failed"
    )

def first_open_get_environment(environment_path="servo-config.json"):
    if os.path.exists(environment_path):
        with open(environment_path, "r") as env_f:
            data = json.load(env_f)
        return data.get("target_environment", {}).get("environment", "None")
    else:
        return "None"

def set_or_replace_arg(args_list, key, value):
    if key in args_list:
        index = args_list.index(key)
        args_list[index + 1] = value
    else:
        args_list += [key, value]

def get_bucket_id(env_bucket_id, env_name):
    if env_name not in env_index_map:
        raise ValueError(f"Unknown environment: {env_name}")
    index = env_index_map[env_name]
    if index >= len(env_bucket_id["bucket_id"]):
        raise IndexError(
            f"env_bucket_id['bucket_id'] has only {len(env_bucket_id['bucket_id'])} items, "
            f"but tried to access index {index}"
        )
    return env_bucket_id["bucket_id"][index]

def get_env_id(env_bucket_id, env_name):
    if env_name not in env_index_map:
        raise ValueError(f"Unknown environment: {env_name}")
    index = env_index_map[env_name]
    if index >= len(env_bucket_id["env_id"]):
        raise IndexError(
            f"env_bucket_id['bucket_id'] has only {len(env_bucket_id['bucket_id'])} items, "
            f"but tried to access index {index}"
        )
    return env_bucket_id["env_id"][index]

def log_build_time_history(build_time_history, label, elapsed):
    def insert():
        build_time_history.configure(state="normal")
        build_time_history.insert(tk.END, f"{label}: {elapsed:.2f}s\n")
        build_time_history.see(tk.END)
        build_time_history.configure(state="disabled")
    build_time_history.after(0, insert)

def force_remove_readonly(func, path, exc_info):
    os.chmod(path, stat.S_IWRITE)
    func(path)
    
def delete_dirs_by_env_id(text_widget, ccd_path, env_bucket_id, current_env):
    if current_env not in env_index_map:
        write_to_console(f"[FAILED] Unknown environment: {current_env}", None, text_widget)
        return
    target_env_id = env_bucket_id["env_id"][env_index_map[current_env]]
    write_to_console(f"[INFO] Target env_id: {target_env_id}", None, text_widget)
    for folder in os.listdir(ccd_path):
        folder_path = os.path.join(ccd_path, folder)
        if not os.path.isdir(folder_path):
            continue
        if target_env_id in folder:
            try:
                shutil.rmtree(folder_path, onerror=force_remove_readonly)
                write_to_console(f"[SUCCESS] Deleted folder: {folder_path}", None, text_widget)
            except Exception as e:
                write_to_console(f"[FAILED] Failed to delete {folder_path}: {e}", None, text_widget)

def encrypt_file_lines_in_place(file_path):
    key = Fernet.generate_key()
    fernet = Fernet(key)
    print(f"[✓] Session Key:\n{key.decode()}\nSave this key if you want to decrypt later.")
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    encrypted_lines = [fernet.encrypt(line.strip().encode()).decode() + "\n" for line in lines]
    with open(file_path, "w", encoding="utf-8") as f:
        f.writelines(encrypted_lines)
    print(f"[✓] Encrypted lines saved to {file_path}")

def decrypt_file_lines_in_place(file_path, key_string):
    try:
        key = key_string.encode()
        fernet = Fernet(key)
    except Exception as e:
        print(f"[✗] Invalid key: {e}")
        return [e]
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    decrypted_lines = []
    for line in lines:
        try:
            decrypted = fernet.decrypt(line.strip().encode()).decode()
            decrypted_lines.append(decrypted)
        except Exception as e:
            print(f"[✗] Failed to decrypt line: {line.strip()} — {e}")
            return [e]
    return decrypted_lines

def get_keystore_info_by_env(env: str, config: dict, decrypted_pass_list: list):
    env = env.strip().upper()
    path_key = f"{env}_KEYSTORE_PATH"
    pass_key = f"{env}_KEYSTORE_PASS"
    path_value = config["PATHS"].get(path_key)
    index_map = {"QA": 0, "PRODUCTION":1, "STAGING":2, "DEVELOP":3}
    index = index_map.get(env)
    if index is None:
        raise ValueError(f"Invalid environment {env}")
    decrypted_pass = decrypted_pass_list[index] if index < len(decrypted_pass_list) else None
    return {
        "env": env,
        "path_key": path_key,
        "path_value": path_value,
        "pass_key": pass_key,
        "pass_value": decrypted_pass
    }

def write_environment(select_env, environment_path="servo-config.json"):
    payload_path = os.path.join(script_dir, environment_path)
    if os.path.exists(payload_path):
        with open(payload_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {}
    data["target_environment"] = {"environment": select_env}
    with open(payload_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    return select_env

def clean_build(project_path):
    dirs_to_delete = ["Library",
                      "Temp", 
                      "Obj",
                      "builds"]
    for relative_dir in dirs_to_delete:
        full_path = os.path.join(project_path, relative_dir)
        if os.path.isdir(full_path):
            print(f"[CLEANUP] Deleting: {full_path}")
            shutil.rmtree(full_path)
        else:
            print(f"[CLEANUP] Not found, skipping: {full_path}")

def fix_file_ownership(project_path, text_widget, target_user="dreamteamadmin"):
    write_to_console("START FIXING FILE OWNERSHIP", None, text_widget)
    try:
        subprocess.run(["sudo", "chown", "-R", "dreamteamadmin", project_path], check=True)
        write_to_console(f"[FIX] Ownership restored to {target_user}", None, text_widget)
    except subprocess.CalledProcessError as e:
        write_to_console(f"[ERROR] Failed to restore ownership: {e}", None, text_widget)
    write_to_console("END FIXING FILE OWNERSHIP", None, text_widget)

#----------------------------------------------------------------
#GitHub - START
def get_current_branch(project_path):
    try:
        result = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, text=True, cwd=project_path)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}")
        return "Unknown"

def clear_local_changes(project_path, text_widget=None):
    try:
        check = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        write_to_console("[GIT CHECK]", check, text_widget)
        if check.stdout.strip():
            reset = subprocess.run(
                ["git", "reset", "--hard"],
                cwd=project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            write_to_console("[GIT RESET]", reset, text_widget)
            clean = subprocess.run(
                ["git", "clean", "-fd"],
                cwd=project_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True
            )
            write_to_console("[GIT CLEAN]", clean, text_widget)
            return True
        return False
    except subprocess.CalledProcessError as ex:
        servo.build_log(ex)
        return False

def checkout_specific_branch(text_widget, project_path, branch_name, remote_name="origin"):
    try:
        clean_branch = branch_name.split("] ", 1)[-1] if "] " in branch_name else branch_name
        remote_branch = f"{remote_name}/{clean_branch}"
        subprocess.run(["git", "fetch", "--all"], cwd=project_path, check=True)
        local_result = subprocess.run(["git", "branch"], cwd=project_path, check=True, stdout=subprocess.PIPE)
        local_branches = [b.strip().lstrip("* ") for b in local_result.stdout.decode().splitlines()]
        remote_result = subprocess.run(["git", "branch", "-r"], cwd=project_path, check=True, stdout=subprocess.PIPE)
        remote_branches = [b.strip() for b in remote_result.stdout.decode().splitlines()]
        if clean_branch in local_branches:
            subprocess.run(["git", "checkout", clean_branch], cwd=project_path, check=True)
            if remote_branch in remote_branches:
                subprocess.run(["git", "pull", remote_name, clean_branch], cwd=project_path, check=True)
                write_to_console("[GIT]", None, text_widget, f"Checked out local branch '{clean_branch}' and pulled latest from remote")
            else:
                write_to_console("[GIT]", None, text_widget, f"Checked out local-only branch '{clean_branch}' (no remote branch to pull)")
            return True
        elif remote_branch in remote_branches:
            subprocess.run(["git", "checkout", "-b", clean_branch, remote_branch], cwd=project_path, check=True)
            write_to_console("[GIT]", None, text_widget, f"Created and checked out local branch '{clean_branch}' from remote '{remote_branch}'")
            return True
        else:
            write_to_console("[GIT]", None, text_widget, f"Branch '{clean_branch}' not found locally or on remote.")
            return False
    except subprocess.CalledProcessError as e:
        write_to_console("[GIT]", None, text_widget, f"{e.cmd}\nReturn Code: {e.returncode}\nError:\n{e.stderr}")
        return False

def checkout_or_create_branch(text_widget, project_path, version_tag, main_branch="main", remote_name="origin"):
    remote_branch = f"{remote_name}/dev/{version_tag}"
    local_branch = f"dev/{version_tag}"
    local_branch_main = f"dev/{main_branch}"
    try:
        current_branch = get_current_branch(project_path)
        if not current_branch.startswith("dev/"):
            return True
        subprocess.run(["git", "fetch", "--all"], cwd=project_path, check=True)
        local_result = subprocess.run(["git", "branch"], cwd=project_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        local_branches = [b.strip().lstrip("* ") for b in local_result.stdout.decode().splitlines()]
        remote_result = subprocess.run(["git", "branch", "-r"], cwd=project_path, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        remote_branches = [b.strip() for b in remote_result.stdout.decode().splitlines()]
        if local_branch in local_branches:
            write_to_console("[GIT]", None, text_widget, f"Local branch '{local_branch}' exists. Checking it out.")
            subprocess.run(["git", "checkout", local_branch], cwd=project_path, check=True)
            if remote_branch in remote_branches:
                subprocess.run(["git", "pull", remote_name, f"dev/{version_tag}"], cwd=project_path, check=True)
            time.sleep(5)
            return True
        if remote_branch in remote_branches:
            write_to_console("[GIT]", None, text_widget, f"Creating local branch '{local_branch}' from remote '{remote_branch}'.")
            subprocess.run(["git", "checkout", "-b", local_branch, remote_branch], cwd=project_path, check=True)
            time.sleep(5)
            return True
        if local_branch_main in local_branches:
            write_to_console("[GIT]", None, text_widget, f"Falling back to '{local_branch_main}'...")
            subprocess.run(["git", "checkout", local_branch_main], cwd=project_path, check=True)
            time.sleep(5)
            return True
        else:
            write_to_console("[GIT]", None, text_widget, f"Neither target nor fallback branch exists: '{local_branch}' / '{remote_branch}' / '{local_branch_main}'")
            time.sleep(5)
            return False
    except subprocess.CalledProcessError as e:
        err = e.stderr.decode().strip() if e.stderr else "<no stderr>"
        servo.build_log(err)
        write_to_console("[GIT]", None, text_widget, f"{e.cmd}\nReturn Code: {e.returncode}\nError:\n{err}")
        return False

def get_all_git_branches_labeled(project_path):
    try:
        result = subprocess.run(
            ["git", "branch", "-a"],
            cwd=project_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        branches = set()
        for line in result.stdout.splitlines():
            clean_line = line.strip().replace("* ", "")
            branches.add(clean_line)
        return sorted(branches)
    except subprocess.CalledProcessError as e:
        return []

def get_current_branch_head(project_path, length=7, unique=True):
    try:
        if unique:
            cmd = ["git", "rev-parse", f"--short={int(length)}", "HEAD"]
            return subprocess.check_output(cmd, cwd=project_path, text=True).strip()
        full_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=project_path, text=True).strip()
        return full_sha[:length]
    except subprocess.CalledProcessError:
        return ""

def check_git_lfs(text_widget, project_path):
    try:
        process_git_lfs = subprocess.run(["git", "lfs", "install"], cwd=project_path, timeout=5, capture_output=True, text=True)
        process_git_status = subprocess.run(["git", "status", "--porcelain"], cwd=project_path, timeout=5, capture_output=True, text=True)
        process_git_rev_parse = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_path, timeout=5, capture_output=True, text=True)
        write_to_console("[GIT]", None, text_widget, "Git environment validated.")
        write_to_console("[GIT]", process_git_lfs, text_widget)
        write_to_console("[GIT]", process_git_status, text_widget)
        write_to_console("[GIT]", process_git_rev_parse, text_widget)
        return True
    except Exception as e:
        servo.build_log(str(e))
        write_to_console("[GIT]", None, text_widget, f"Error {e}.")
        return False
#GitHub -END
#----------------------------------------------------------------
#Safeguard - START
def wait_for_project_unlock(project_path, text_widget, timeout=15):
    lock_file = os.path.join(project_path, "Temp", "UnityLockfile")
    start = time.time()
    while os.path.exists(lock_file):
        if time.time() - start > timeout:
            write_to_console("[WARNING] Unity lock file not released in time.", None, text_widget)
            return False
        time.sleep(0.5)
    return True

def safeguard_launcher(label, cmd, text_widget, project_path, led=None,
                       build_time_history=None, success_msg=None, failure_msg=None):
    silence_timeout = 3 * 60
    full_cmd = list(cmd) + ["-projectPath", project_path]
    popen_kwargs = (
        {'start_new_session': True} if os.name == 'posix'
        else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
    )
    proc = subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        **popen_kwargs
    )
    if led and hasattr(led, "start_blink"):
        text_widget.after(0, led.start_blink)
    time.sleep(1)
    if proc.poll() is not None:
        write_to_console("[ERROR] Subprocess exited immediately.", None, text_widget)
        if proc.stdout:
            error_output = proc.stdout.read().strip()
            proc.stdout.close()
        else:
            error_output = "[ERROR] proc.stdout was None."
        return 1, [error_output]    
    start_time = time.perf_counter()
    last_output_time = start_time
    output_lines = []
    try:
        if proc.stdout is None:
            raise ValueError("proc.stdout is None — cannot read output.")
        for line in iter(proc.stdout.readline, ''):
            now = time.perf_counter()
            if now - last_output_time > silence_timeout:
                write_to_console(
                    f"[WARNING] No output for {silence_timeout / 60:.0f} min; killing Unity…",
                    None,
                    text_widget
                )
                proc.kill()
                break
            last_output_time = now
            line = line.rstrip("\n")
            output_lines.append(line)
            write_to_console(line, proc, text_widget)
    except ValueError as ve:
        write_to_console(f"[ERROR] {ve}", None, text_widget)
        proc.kill()
        return 1, [str(ve)]
    finally:
        proc.stdout.close()
        ret = proc.wait()
        if led and hasattr(led, "stop_blink"):
            text_widget.after(0, led.stop_blink)
    total_elapsed = time.perf_counter() - start_time
    if ret == 0:
        write_to_console(label, None, text_widget, success_msg=success_msg)
        if build_time_history:
            log_build_time_history(build_time_history, label, total_elapsed)
        return 0, output_lines
    else:
        msg = failure_msg or f"[ERROR] {label} build failed (rc={ret})."
        write_to_console(label, None, text_widget, failure_msg=msg)
        return ret, output_lines
#Safeguard - END
#----------------------------------------------------------------
#Player Prefs and Keystore - START
def get_environment(short=False) -> str:
    base_dir = os.path.dirname(__file__)
    main_payload = os.path.join(base_dir, "servo-config.json")
    if not os.path.exists(main_payload):
        print(f"[WARN] servo-config.json not found at {main_payload}")
        return ""
    with open(main_payload, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    env = payload.get("target_environment", {}).get("environment", "")
    if not env:
        print("[WARN] 'target_environment.environment' not set in servo-config.json")
        return ""
    if short:
        return env[:-4].lower() if env.endswith("_ENV") else env.lower()
    return env

def add_player_pref(text_widget, build_time_history, unity_path, project_path, player_prefs, led):
    build_args = [
        unity_path,
        "-batchmode",
        "-quit",
        "-projectPath", project_path,
        "-executeMethod", "ScriptingBuilderHelpers.AddPlayerPref",
        "--value1", json.dumps(player_prefs),
        "-logFile", "-"
    ]
    ret_rebuild, output = safeguard_launcher(
        "Add player prefs", build_args, text_widget, project_path,
        led, build_time_history,
        success_msg="[SUCCESS] Add Player Prefs",
        failure_msg="[FAILED] Add Player Prefs failed."
    )
#Player Prefs and Keystore - END
#----------------------------------------------------------------
#Sequancing action - START
def sequencing_actions(text_widget, steps):
    for label, func in steps:
        write_to_console(f"[BUILD] Starting: {label}\n", None, text_widget)
        func() 
        write_to_console(f"[BUILD] Finished: {label}\n", None, text_widget)
#Sequancing action - END
#----------------------------------------------------------------
#Snapshot - START
EXCLUDES=["ProjectSettings/", "Tools/"]
def make_snapshot(project_path):
    system = platform.system()
    snapshot = tempfile.mkdtemp(prefix="unity_snapshot_")
    def py_copy(src, dst):
        for item in os.listdir(src):
            if any(item == e.rstrip("/") for e in EXCLUDES):
                continue
            s = os.path.join(src, item)
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                shutil.copytree(s, d, symlinks=True)
            else:
                shutil.copy2(s, d)
    try:
        if system in ("Linux", "Darwin"):
            cmd = ["rsync", "-a", "--delete"]
            for e in EXCLUDES:
                cmd += ["--exclude", e]
            cmd += [f"{project_path}/", snapshot]
            subprocess.check_call(cmd)
        elif system == "Windows":
            cmd = ["robocopy",
                   project_path.replace("/", "\\"), 
                   snapshot.replace("/", "\\"), 
                   "/MIR"]
            for e in EXCLUDES:
                cmd += ["/XD", os.path.join(project_path, e.rstrip("/")).replace("/", "\\")]
            rc = subprocess.call(cmd)
            if rc >= 8:
                raise subprocess.CalledProcessError(rc, cmd)
        else:
            raise RuntimeError("Unsupported OS")
    except Exception:
        shutil.rmtree(snapshot)
        os.makedirs(snapshot, exist_ok=True)
        py_copy(project_path, snapshot)
    return snapshot

def restore_snapshot(snapshot, project_path):
    system = platform.system()
    def py_restore():
        for name in os.listdir(project_path):
            if any(name == e.rstrip("/") for e in EXCLUDES):
                continue
            full = os.path.join(project_path, name)
            if os.path.isdir(full):
                shutil.rmtree(full)
            else:
                os.remove(full)
        for name in os.listdir(snapshot):
            src = os.path.join(snapshot, name)
            dst = os.path.join(project_path, name)
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=True)
            else:
                shutil.copy2(src, dst)
    try:
        if system in ("Linux", "Darwin"):
            cmd = [
                "rsync", "-a", "--delete",
                "--exclude", "ProjectSettings/",
                "--exclude", "Tools/",
                f"{snapshot}/", project_path
            ]
            subprocess.check_call(cmd)
            shutil.rmtree(snapshot)
            return
        if system == "Windows":
            src = snapshot.replace("/", "\\")
            dst = project_path.replace("/", "\\")
            cmd = ["robocopy", src, dst, "/MIR"]
            for e in EXCLUDES:
                cmd += ["/XD", os.path.join(dst, e.rstrip("/"))]
            code = subprocess.call(cmd)
            if code < 8:
                shutil.rmtree(snapshot)
                return
    except Exception:
        pass
    py_restore()
    try:
        shutil.rmtree(snapshot)
    except Exception as e:
        print(f"[restore_snapshot] warning: could not delete snapshot: {e}")
#Snapshot - END
#----------------------------------------------------------------
#Upload AAB to Google Play Console - START
SCOPES = ["https://www.googleapis.com/auth/androidpublisher"]
def is_app_reviewed(service, package_name, edit_id):
    try:
        tracks = service.edits().tracks().list(packageName=package_name, editId=edit_id).execute()
        for track in tracks.get("tracks", []):
            for release in track.get("releases", []):
                if release.get("status") == "completed":
                    return True
        return False
    except Exception:
        return False
def get_version_code(environment, text_widget=None):
    env = env_shorthand_name_map[environment]
    package_name = package_map[env]
    credential = os.path.join(script_dir, "cryptic", "dreamteam-ch-dev-8ab8ad353128.json")
    creds = service_account.Credentials.from_service_account_file(credential, scopes=SCOPES)
    service = build("androidpublisher", "v3", credentials=creds)
    if text_widget is not None:
        write_to_console("[Android Upload]", None, text_widget, f"Authenticating and fetching version for {package_name}")
    edit = service.edits().insert(packageName=package_name, body={}).execute()
    edit_id = edit["id"]
    track = service.edits().tracks().get(
        packageName=package_name, editId=edit_id, track="internal"
    ).execute()
    releases = track.get("releases", [])
    seqs = []
    for r in releases:
        name = r.get("name", "")
        m = re.match(r"^(\d+)", name)
        if m:
            seqs.append(int(m.group(1)))
    last = max(seqs) if seqs else 0
    version = str(last + 1)
    if text_widget is not None:
        write_to_console("[Android Upload]", None, text_widget, f"Next version code will be: {version}")
    return version

def upload_and_promote(text_widget, creds, package_name, version_name, aab_path):
    service = build("androidpublisher", "v3", credentials=creds)
    edit = service.edits().insert(packageName=package_name, body={}).execute()
    edit_id = edit["id"]
    write_to_console("[Android Upload]", None, text_widget, f"Uploading AAB: {aab_path}")
    media = MediaFileUpload(str(aab_path), mimetype="application/octet-stream", resumable=True)
    result = service.edits().bundles().upload(
        packageName=package_name,
        editId=edit_id,
        media_body=media
    ).execute()
    version_code = result["versionCode"]
    status = "draft"
    release_notes = [
        {"language": "ja-JP", "text": "本リリースは、社内開発およびフィードバック収集を目的としています。開発環境でのテストのための主要な機能が含まれています。今後のリリースに向けた改善のため、皆様のご意見をお待ちしております。"},
        {"language": "en-US", "text": "This release is for internal development and feedback purposes. It includes core features for testing in the development environment. Your input is valuable in refining the app for future releases."},
    ]
    service.edits().tracks().update(
        packageName=package_name,
        editId=edit_id,
        track="internal",
        body={
            "releases": [{
                "name": f"{version_code} ({version_name})",
                "versionCodes": [version_code],
                "status": status,
                "releaseNotes": release_notes
            }]
        }
    ).execute()
    try:
        service.edits().commit(packageName=package_name, editId=edit_id).execute()
    except HttpError as e:
        if "Only releases with status draft may be created on draft app" in str(e):
            write_to_console("[Android Upload]", None, text_widget, "[✗] App is still a draft in Google Play Console. You must submit it manually at least once for review.")
        raise
    write_to_console("[Android Upload]", None, text_widget, f"Uploaded and {status.upper()} version {version_code}")

def publish_android(text_widget, environment=None, version_code=None, version_name=None, note=None):
    env = env_shorthand_name_map[environment]
    package_name = package_map[env]
    system = platform.system()
    base = Path("C:/cdc-builds/") if system == "Windows" else Path.home() / f"Projects/builds/Android/{env}"
    glob_dir = base / f"ch-client-{env}-{version_code}-{version_name}_{note}"
    write_to_console("[Android Upload]", None, text_widget, f"[→] Locating AAB in: {glob_dir}")
    matches = list(glob_dir.glob("*.aab"))
    if not matches:
        msg = f"[✗] No AAB found in {glob_dir}"
        write_to_console("[Android Upload]", None, text_widget, msg)
        raise FileNotFoundError(msg)
    if len(matches) > 1:
        msg = f"[✗] Multiple AABs found in {glob_dir}: {matches}"
        write_to_console("[Android Upload]", None, text_widget, msg)
        raise RuntimeError(msg)
    aab_path = matches[0]
    if not aab_path.is_file():
        msg = f"[✗] AAB not found at {aab_path}"
        write_to_console("[Android Upload]", None, text_widget, msg)
        raise FileNotFoundError(msg)
    credential = os.path.join(script_dir, "cryptic", "dreamteam-ch-dev-8ab8ad353128.json")
    creds = service_account.Credentials.from_service_account_file(credential, scopes=SCOPES)
    write_to_console("[Android Upload]", None, text_widget, f"[✓] Credential loaded from {credential}")
    upload_and_promote(text_widget, creds, package_name, version_name, aab_path)
#Upload AAB to Google Play Console - END
#----------------------------------------------------------------
#Upload to xcode - START
def find_workspace_or_project(project_path):
    xcworkspace = next(project_path.rglob("*.xcworkspace"), None)
    xcodeproj = next(project_path.rglob("*.xcodeproj"), None)
    if xcworkspace:
        return xcworkspace, True
    elif xcodeproj:
        return xcodeproj, False
    else:
        raise FileNotFoundError("No .xcworkspace or .xcodeproj found")

def archive_ios(text_widget, project_path, archive_path, workspace):
    cmd = [
        "xcodebuild",
        "-scheme", "Unity-iPhone",
        "-configuration", "Release",
        "-sdk", "iphoneos",
        "-archivePath", str(archive_path),
        "archive",
        "-allowProvisioningUpdates",
        "-verbose"
    ]
    if workspace:
        xcworkspace = next(project_path.rglob("*.xcworkspace"))
        cmd.insert(1, str(xcworkspace))
        cmd.insert(1, "-workspace")
    else:
        xcodeproj = next(project_path.rglob("*.xcodeproj"))
        cmd.insert(1, str(xcodeproj))
        cmd.insert(1, "-project")
    write_to_console(f"[→] Running archive command:\n{' '.join(cmd)}", None, text_widget)
    result = subprocess.run(cmd, check=True, text=True, capture_output=True)
    write_to_console("[ARCHIVE iOS]", result, text_widget)
    if result.stderr:
        write_to_console("[ARCHIVE iOS]", result, text_widget)

def create_export_options_plist(plist_path, team_id=None):
    options = {
        "method": "app-store",
        "signingStyle": "automatic",
        "uploadBitcode": False,
        "uploadSymbols": True,
    }
    if team_id:
        options["teamID"] = team_id
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    with plist_path.open("wb") as f:
        plistlib.dump(options, f)

def export_ipa(text_widget, archive_path, export_path, plist_path):
    result = subprocess.run([
        "xcodebuild",
        "-exportArchive",
        "-archivePath", str(archive_path),
        "-exportPath", str(export_path),
        "-exportOptionsPlist", str(plist_path)
    ], check=True, text=True, capture_output=True)
    write_to_console("[EXPORT IPA]", result, text_widget)
    if result.stderr:
        write_to_console("[EXPORT IPA]", result, text_widget)

def upload_to_testflight(text_widget, ipa_path):
    result = subprocess.run([
        "xcrun", "altool",
        "--upload-app",
        "-f", str(ipa_path),
        "-t", "ios",
        # "-u", "w-faiz@okakichi.co.jp",
        # "-p", "adpq-ztwq-coys-udrx",
        "-u", "w-faiz@okakichi.co.jp",
        "-p", "bghz-rcfm-azhx-wamz",
        "--verbose"
    ], check=True, text=True, capture_output=True)
    write_to_console("[UPLOAD TESTFLIGHT]", result, text_widget)
    if result.stderr:
        write_to_console("[UPLOAD TESTFLIGHT]", result, text_widget)

def publish_ios(text_widget, environment=None, version_name=None, note=None):
    system = platform.system()
    env = env_shorthand_name_map[environment]
    if system == "Windows":
        build_base = Path("C:/cdc-builds")
    else:
        build_base = Path.home() / f"Projects/builds/iOS/{env}"
    build_dir = build_base / f"ch-client-{env}-{version_name}_{note}"
    if not build_dir.exists():
        raise FileNotFoundError(f"Expected iOS build directory not found: {build_dir}")
    archive_path = build_dir / "Unity-iPhone.xcarchive"
    export_path =build_dir / "Export"
    plist_path = build_dir / "ExportOptions.plist"
    target, is_workspace = find_workspace_or_project(build_dir)
    archive_ios(text_widget, build_dir, archive_path, is_workspace)
    create_export_options_plist(plist_path)
    export_ipa(text_widget, archive_path, export_path, plist_path)
    ipa_files = list(export_path.glob("*.ipa"))
    if not ipa_files:
        raise FileNotFoundError("No .ipa file found after export")
    ipa_path = ipa_files[0]
    upload_to_testflight(text_widget, ipa_path)
    write_to_console("[iOS Upload]", None, text_widget, "Upload to TestFlight complete.")
# Upload to xcode - END
#----------------------------------------------------------------
# Patching Environment Addressable - START
def prepare_and_patch_addressable(current_env, version, source_root, target_platform):
    env_keys = ["dev", "qa", "staging", "production"]
    current_env_id = env_name_map[current_env]
    current_bucket_id = bucket_name_map[current_env]
    current_env_short = env_shorthand_name_map[current_env]
    copy_path = os.path.join(source_root, current_env_id, current_bucket_id, "latest", target_platform)
    if not os.path.exists(copy_path):
        raise FileNotFoundError(f"Source folder not found: {copy_path}")
    for target_env in env_keys:
        target_env_long = env_longhand_name_map[target_env]
        if current_env == target_env_long:
            continue
        target_env_id = env_name_map[target_env_long]
        target_bucket_id = bucket_name_map[target_env_long]
        output_path = os.path.join(source_root, target_env_id, target_bucket_id, "latest", target_platform)
        if os.path.exists(output_path):
            shutil.rmtree(output_path)
        shutil.copytree(copy_path, output_path)
        catalog_filename = f"catalog_{version}.json"
        catalog_path = os.path.join(output_path, catalog_filename)
        if not os.path.exists(catalog_path):
            raise FileNotFoundError(f"Missing catalog file: {catalog_path}")
        with open(catalog_path, "r", encoding="utf-8") as f:
            data = f.read()
        data = data.replace(f"/{current_bucket_id}/", f"/{target_bucket_id}/")
        for env_key in env_keys:
            from_env = "develop" if env_key == "dev" else env_key
            to_env = "develop" if target_env == "dev" else target_env
            data = data.replace(f"/{from_env}/", f"/{to_env}/")
            data = data.replace(f"icon-{current_env_short}.png", f"icon-{target_env}.png")
        with open(catalog_path, "w", encoding="utf-8") as f:
            f.write(data)
        hash_filename = f"catalog_{version}.hash"
        hash_path = os.path.join(output_path, hash_filename)
        sha = hashlib.sha256(data.encode("utf-8")).hexdigest()
        with open(hash_path, "w", encoding="utf-8") as f:
            f.write(sha)
# Patching Environment Addressable - END
#----------------------------------------------------------------
# Upload tp Unity CCD through CLI - START
def create_headers(user, key):
    tok = base64.b64encode(f"{user}:{key}".encode()).decode()
    return {
        "Authorization": f"Basic {tok}",
        "Accept": "application/json",
        "x-upload-client": "unity-cloud-content-uploader"
    }

def delete_all_entries(text_widget, project_id, entrie_name, env_id, bucket_id, headers):
    write_to_console("[DELETE]", None, text_widget, "Deleting all entries…")
    page = 1
    while True:
        url = (
            f"https://services.api.unity.com/ccd/management/v1/"
            f"projects/{project_id}/environments/{env_id}/buckets/{bucket_id}"
            f"/entries?per_page=100&page={page}"
        )
        r = session.get(url, headers=headers)
        if not r.ok or r.status_code == 416:
            break
        batch = r.json()
        if not batch:
            break
        for e in batch:
            if e["path"].startswith(f"{entrie_name}/"):
                durl = (
                    f"https://services.api.unity.com/ccd/management/v1/"
                    f"projects/{project_id}/environments/{env_id}/buckets/{bucket_id}"
                    f"/entries/{e['entryid']}"
                )
                dr = session.delete(durl, headers=headers)
                write_to_console("[DELETE]", None, text_widget, f"[✓] Deleted: {e['path']}" if dr.ok else f"[✗] Delete failed: {e['path']}")
        page += 1
    time.sleep(1)

def get_ugs_executable():
    if platform.system() == "Windows":
        return r"C:\Users\User\AppData\Roaming\npm\node_modules\ugs\bin\ugs.exe"
    else:
        return shutil.which("ugs") or "/usr/local/bin/ugs"

def ensure_ugs_logged_in(text_widget, key_id, secret_key):
    if platform.system() == "Windows":
        config_path = Path(os.getenv("APPDATA")) / "ugs-cli" / "config.json"
    else:
        config_path = Path.home() / ".ugs-cli" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            if "credentials" in config and config["credentials"].get("key_id") == key_id:
                return True
        except Exception as e:
            write_to_console("[UGS LOGIN]", None, text_widget, f"[!] Failed to parse UGS config: {e}")
    ugs_exe = get_ugs_executable()
    if not os.path.isfile(ugs_exe):
        write_to_console("[UGS LOGIN]", None, text_widget, f"UGS CLI not found at: {ugs_exe}")
        return False
    try:
        args = [ugs_exe, "login", "--service-key-id", key_id, "--secret-key-stdin"]
        process = subprocess.run(
            args,
            input=secret_key,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        write_to_console("[UGS LOGIN]", process, text_widget)
        if process.returncode != 0:
            write_to_console("[UGS LOGIN]", process, text_widget)
            return False
        return True
    except Exception as e:
        write_to_console("[UGS LOGIN]", None, text_widget, f"Exception during login: {e}")
        return False

def upload_ccd_cli(text_widget, project_path, unity_cloud_username, unity_cloud_api_key, project_id, current_env, ccd_path, entrie_name,
                   *, version=None, create_release=False):
    try:
        if not ensure_ugs_logged_in(text_widget, unity_cloud_username, unity_cloud_api_key):
            write_to_console("[CCD UPLOAD]", None, text_widget, "Login failed or UGS CLI not found.")
            return False
        env_id   = env_name_map.get(current_env)
        bucket_id = bucket_name_map.get(current_env)
        env_name = ccd_environment_map.get(current_env)
        if not (env_id and bucket_id and env_name):
            write_to_console("[CCD UPLOAD]", None, text_widget, f"Bad env/bucket mapping for key: {current_env}")
            return False
        local_path = os.path.join(project_path, ccd_path, env_id, bucket_id, "latest", entrie_name)
        if not os.path.isdir(local_path):
            write_to_console("[CCD UPLOAD]", None, text_widget, f"Missing dir: {local_path}")
            return False
        env = os.environ.copy()
        env["UGS_CLI_PROJECT_ID"] = project_id
        env["UGS_CLI_ENVIRONMENT_NAME"] = env_name
        env["UGS_CLI_BUCKET_NAME"] = "client-resources"
        ugs_exe = get_ugs_executable()
        if not os.path.isfile(ugs_exe):
            write_to_console("[CCD UPLOAD]", None, text_widget, f"UGS CLI not found at: {ugs_exe}")
            return False
        headers = create_headers(unity_cloud_username, unity_cloud_api_key)
        delete_all_entries(text_widget, project_id, entrie_name, env_id, bucket_id, headers)
        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, entrie_name)
            shutil.copytree(local_path, dest_path)
            args = [ugs_exe, "ccd", "entries", "sync", temp_dir]
            if create_release:
                git_header = get_current_branch_head(project_path, unique=True)
                badge_name = re.sub(r'[^A-Za-z0-9_-]+', '-', str(version)).strip('-')
                notes = f'"v{version} #{git_header}"'
                args = [
                    ugs_exe, "ccd", "entries", "sync", temp_dir,
                    "--create-release",
                    "--badge", badge_name,
                    "--release-notes", notes,
                ]
            proc = subprocess.run(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            write_to_console("[CCD UPLOAD]", proc, text_widget)
            ok = (proc.returncode == 0)
            if not ok:
                write_to_console("[CCD UPLOAD]", None, text_widget, f"Failed for {env_id}: {proc.stderr.strip()}")
            else:
                write_to_console("[CCD UPLOAD]", None, text_widget, f"Done with {env_id}" + (f" (release badge='{badge_name}')" if create_release else ""))
            return ok
    except Exception as e:
            servo.build_log(str(e))

def upload_to_production(text_widget, project_path, unity_cloud_username, unity_cloud_api_key, project_id, entrie_name, current_env, ccd_path):
    if current_env == "PRODUCTION_ENV":
        if not ensure_ugs_logged_in(text_widget, unity_cloud_username, unity_cloud_api_key):
            write_to_console("[CCD UPLOAD]", None, text_widget, "Login failed or UGS CLI not found.")
            return
        env_id = env_name_map.get(current_env)
        bucket_id = bucket_name_map.get(current_env)
        env_name = ccd_environment_map.get(current_env)
        local_path = os.path.join(project_path, ccd_path, env_id, bucket_id, "latest", entrie_name)
        if not os.path.isdir(local_path):
            return
        headers = create_headers(unity_cloud_username, unity_cloud_api_key)
        delete_all_entries(text_widget, project_id, entrie_name, env_id, bucket_id, headers)
        env = os.environ.copy()
        env["UGS_CLI_PROJECT_ID"] = project_id
        env["UGS_CLI_ENVIRONMENT_NAME"] = env_name
        env["UGS_CLI_BUCKET_NAME"] = "client-resources"
        ugs_exe = get_ugs_executable()
        if not os.path.isfile(ugs_exe):
            write_to_console("[CCD UPLOAD]", None, text_widget, f"UGS CLI not found at: {ugs_exe}")
            return
        with tempfile.TemporaryDirectory() as temp_dir:
            dest_path = os.path.join(temp_dir, entrie_name)
            shutil.copytree(local_path, dest_path)
            args = [ugs_exe, "ccd", "entries", "sync", temp_dir]
            process = subprocess.run(
                args,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            write_to_console("[CCD UPLOAD]", process, text_widget)
            if process.returncode != 0:
                write_to_console("[CCD UPLOAD]", None, text_widget, f"Failed to upload for {env_id}:")
            else:
                write_to_console("[CCD UPLOAD]", None, text_widget, f"Done with {env_id}")

def download_ccd_cli(text_widget, unity_cloud_username, unity_cloud_api_key, project_id, entrie_name, current_env, output_dir,
                     which_release=2, prefixes=None, exts=(".json", ".hash", ".bundle", ".bin")):
    if not ensure_ugs_logged_in(text_widget, unity_cloud_username, unity_cloud_api_key):
        write_to_console("[CCD DOWNLOAD]", None, text_widget, "Login failed or UGS CLI not found.")
        return
    env_name = ccd_environment_map.get(current_env, current_env)
    bucket_id = bucket_name_map.get(current_env)
    bucket_token = bucket_token_map.get(current_env)
    if not env_name:
        write_to_console("[CCD DOWNLOAD]", None, text_widget, f"env_name not found for key: {current_env}")
        return
    if not bucket_id:
        write_to_console("[CCD DOWNLOAD]", None, text_widget, f"bucket_id not found for key: {current_env}")
        return
    if prefixes is None:
        p = (entrie_name or "").strip().lower()
        if p == "android":
            prefixes = ("android/",)
        elif p == "ios":
            prefixes = ("ios/",)
        elif p in ("both", ""):
            prefixes = ("android/", "ios/")
        else:
            prefixes = (p if p.endswith("/") else p + "/",)
    def _match_prefix(path: str) -> bool:
        low = (path or "").lower()
        return any(low.startswith((px if px.endswith("/") else px + "/").lower()) for px in (prefixes or ()))
    def _match_ext(path: str) -> bool:
        if not exts: return True
        low = (path or "").lower()
        return any(low.endswith(e.lower()) for e in exts)
    final_root = os.path.join(output_dir, entrie_name)
    Path(final_root).mkdir(parents=True, exist_ok=True)
    ugs_exe = get_ugs_executable()
    if not os.path.isfile(ugs_exe):
        write_to_console("[CCD DOWNLOAD]", None, text_widget, f"UGS CLI not found at: {ugs_exe}")
        return
    def _run(cmd, cwd=None, tag=""):
        proc = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if tag: write_to_console(tag, proc, text_widget)
        return proc
    releases = []
    page = 1
    while True:
        cmd = [
            ugs_exe, "ccd", "releases", "list",
            "-p", project_id,
            "-e", env_name,
            "-b", "client-resources",
            "--json",
            "--per-page", "200",
            "--page", str(page),
        ]
        proc = _run(cmd, tag=f"[CCD DOWNLOAD] releases page {page}")
        if proc.returncode != 0:
            if "invalid page" in proc.stderr.lower() or "requested range not satisfiable" in proc.stderr.lower():
                break
            write_to_console("[CCD DOWNLOAD]", None, text_widget,
                             f"Failed to list releases for {env_name}: {proc.stderr.strip()}")
            return
        out = proc.stdout.strip()
        if not out or out == "null":
            break
        try:
            chunk = json.loads(out)
            if isinstance(chunk, dict) and "results" in chunk:
                chunk = chunk["results"]
        except Exception as ex:
            write_to_console("[CCD DOWNLOAD]", None, text_widget, f"Bad JSON from releases list: {ex}")
            return
        if not chunk:
            break
        releases.extend(chunk)
        page += 1
    if not releases:
        write_to_console("[CCD DOWNLOAD]", None, text_widget, "No releases found.")
        return
    def _relnum(r):
        return int(r.get("ReleaseNum") or r.get("releaseNum") or 0)
    releases.sort(key=_relnum, reverse=True)
    if which_release < 1 or which_release > len(releases):
        write_to_console("[CCD DOWNLOAD]", None, text_widget,
                         f"Not enough releases. Requested #{which_release}, but there are only {len(releases)}.")
        return
    release = releases[which_release - 1]
    release_id = release.get("ReleaseId") or release.get("releaseId")
    relnum = _relnum(release)
    if not release_id:
        write_to_console("[CCD DOWNLOAD]", None, text_widget, "Could not resolve release_id from CLI output.")
        return
    write_to_console("[CCD DOWNLOAD]", None, text_widget, f"Using release #{relnum}: {release_id}")
    host = f"https://{project_id}.client-api.unity3dusercontent.com"
    session = requests.Session()
    if bucket_token:
        user_pass = f":{bucket_token}".encode("utf-8")
        b64 = base64.b64encode(user_pass).decode("ascii")
        session.headers["Authorization"] = f"Basic {b64}"
    session.headers.update({"Accept": "application/json"})
    def iter_release_entries():
        page = 1
        while True:
            params = {"per_page": 200, "page": page}
            url = f"{host}/client_api/v1/buckets/{bucket_id}/releases/{release_id}/entries"
            r = session.get(url, params=params, timeout=(15, 120))
            if r.status_code != 200:
                write_to_console("[CCD DOWNLOAD]", None, text_widget,
                                 f"list (release {release_id}) page {page}: {r.status_code} {r.text[:300]}")
                r.raise_for_status()
            data = r.json()
            items = data if isinstance(data, list) else data.get("results", [])
            if not items: break
            for it in items: yield it
            page += 1
    downloaded = skipped = failed = 0
    for e in iter_release_entries():
        path = e.get("path") or ""
        if not path or not _match_prefix(path) or not _match_ext(path):
            continue
        dest = os.path.join(final_root, path)
        Path(os.path.dirname(dest)).mkdir(parents=True, exist_ok=True)
        size = e.get("content_size")
        if os.path.exists(dest) and (size is None or os.path.getsize(dest) == int(size)):
            skipped += 1
            write_to_console("[CCD DOWNLOAD]", None, text_widget, f"skip (up-to-date): {path}")
            continue
        content_url = f"{host}/client_api/v1/buckets/{bucket_id}/releases/{release_id}/entry_by_path/content"
        params = {"path": path}
        try:
            with session.get(content_url, params=params, stream=True, timeout=(15, 300)) as r:
                r.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in r.iter_content(chunk_size=256 * 1024):
                        if chunk: f.write(chunk)
            downloaded += 1
            write_to_console(f"[CCD DOWNLOAD] {path}", None, text_widget, "ok")
        except Exception as ex:
            failed += 1
            write_to_console("[CCD DOWNLOAD]", None, text_widget, f"fail: {path} → {ex}")
    write_to_console("[CCD DOWNLOAD]", None, text_widget,
                     f"Done {env_name} (release {release_id}) → {final_root}\nDownloaded={downloaded}, Failed={failed}, Skipped={skipped}")
# Upload tp Unity CCD through CLI - END
#----------------------------------------------------------------
# Add ScriptingBuilderHelper.cs - START
def copy_paste_scripting_builder_helper(project_path):
    source = os.path.abspath(r"UnityScripts/ScriptingBuilderHelpers.cs")
    destination_dir = os.path.join(project_path, "Assets", "Editor", "Helpers")
    destination_file = os.path.join(destination_dir, "ScriptingBuilderHelpers.cs")
    if not os.path.exists(source):
        return
    if not os.path.exists(destination_dir):
        return
    if not os.path.exists(destination_file):
        shutil.copy2(source, destination_file)
# Add ScriptingBuilderHelper.cs - END
#----------------------------------------------------------------
# Script Recompile - START
def force_script_recompile(text_widget, build_time_history, unity_path, project_path, led):
    try:
        write_to_console("Start dummy launch to trigger script compile", None, text_widget)
        log_path = os.path.join(project_path, "Temp", "unity_compiler.log")
        subprocess.run([
            unity_path,
            "-batchmode",
            "-projectPath", project_path,
            "-quit",
            "-logFile", log_path
        ], check=True)
        if os.path.exists(log_path):
            with open(log_path) as f:
                log_contents = f.read()
                if "error CS" in log_contents or "error " in log_contents:
                    write_to_console("Unity script compilation failed. See log below:", None, text_widget)
                    write_to_console(log_contents, None, text_widget)
                    raise RuntimeError("Unity compilation failed. Aborting.")
        dll_path = os.path.join(project_path, "Library", "ScriptAssemblies", "Assembly-CSharp-Editor.dll")
        for _ in range(30):
            if os.path.exists(dll_path):
                break
            time.sleep(1)
        else:
            raise TimeoutError("Unity did not compile scripts within 30 seconds.")
        BASE_ARGS = [
            unity_path,
            "-batchmode",
            "-quit",
            "-projectPath", project_path,
            "-executeMethod", "ScriptingBuilderHelpers.ForceScriptRecompile",
        ]
        ret_recompile, output = safeguard_launcher(
            "Recompile script", BASE_ARGS, text_widget, project_path,
            led, build_time_history,
            success_msg="[SUCCESS] Recompile script success",
            failure_msg="[FAILED] Recompile script failed"
        )
    except Exception as e:
        servo.build_log(str(e))
        restore_widget_text_to_normal(text_widget, e)
# Script Recompile - END
#----------------------------------------------------------------
# Remove Orphan .meta - START
def remove_orphan_meta_files(text_widget, project_path):
    meta_files = glob.glob(os.path.join(project_path, 'Packages', 'com.google.play.*', '**', '*.meta'), recursive=True)
    for meta_path in meta_files:
        asset_path = meta_path[:-5]
        if not os.path.exists(asset_path):
            write_to_console("[META CLEANUP]", None, text_widget, f"Removing: {meta_path}")
            try:
                os.remove(meta_path)
            except Exception as e:
                servo.build_log(str(e))
                write_to_console("[META CLEANUP]", None, text_widget, f"Failed to delete {meta_path}: {e}")
# Remove Orphan .meta - END
#----------------------------------------------------------------
# Change App Title - START
def change_correct_app_title(text_widget, project_path, env):
    env_short = env_shorthand_name_map[env]
    json_path = os.path.join(project_path, "ProjectSettings", "LocalizedAppTitle.json")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    updated = False
    for entry in data.get("LocalizedData", []):
        if entry.get("LanguageCode") == "ja":
            entry["AppName"] = f"ちゃんごくし！ヒーローズ ({env_short})"
            entry["AppShortName"] = "ちゃんひー"
            updated = True
    if updated:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        write_to_console("[INJECT TITLE]", None, text_widget, f"Updated Japanese app title at: {json_path}")
    else:
        write_to_console("[INJECT TITLE]", None, text_widget, "No Japanese entry found in LocalizedAppTitle.json")
# change app title - END
#----------------------------------------------------------------
# get iOS version number - START
def get_latest_build_number(env, version, json_path="servo-config.json"):
    if os.path.exists(json_path):
        with open(json_path, "r") as f:
            data = json.load(f)
    else:
        data = {}
    if "iOSBuilVersionNumber" not in data:
        data["iOSBuilVersionNumber"] = {}
    ios_versions = data["iOSBuilVersionNumber"]
    if env not in ios_versions:
        ios_versions[env] = {}
    current_build = ios_versions[env].get(version, -1)
    new_build = current_build + 1
    ios_versions[env][version] = new_build
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2)
    return new_build
# get iOS version number - END
#----------------------------------------------------------------
# Snapshot Unity CCD - START
def ccd_snapshot(text_widget, unity_cloud_username, unity_cloud_api_key, project_id, current_env, entrie_name, output_dir,
                          badge_name="latest", exts=(".json", ".hash", ".bundle", ".bin")):
    try:
        env_name   = ccd_environment_map.get(current_env, current_env)
        bucket_id  = bucket_name_map.get(current_env)
        if not env_name or not bucket_id:
            write_to_console("[CCD DOWNLOAD]", None, text_widget, f"[✗] Bad env/bucket for {current_env}")
            return
        headers = create_headers(unity_cloud_username, unity_cloud_api_key)
        ugs_exe = shutil.which("ugs") or get_ugs_executable()
        if not ugs_exe or not os.path.isfile(ugs_exe):
            write_to_console("[CCD DOWNLOAD]", None, text_widget, "[✗] UGS CLI not found. Install with: npm i -g ugs")
            return
        try:
            ok_login = ensure_ugs_logged_in(text_widget, unity_cloud_username, unity_cloud_api_key)
        except Exception:
            ok_login = False
        if not ok_login:
            write_to_console("[CCD DOWNLOAD]", None, text_widget, "[✗] UGS login failed.")
            return
        rel_id = None
        rel_num = None
        try:
            proc = subprocess.run(
                [ugs_exe, "ccd", "badges", "list",
                 "-p", project_id, "-e", env_name, "-b", "client-resources",
                 "-n", badge_name, "--json"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if proc.returncode == 0 and proc.stdout.strip():
                badge_json = json.loads(proc.stdout.strip())
                if badge_json and isinstance(badge_json, list):
                    rel_num = int(badge_json[0].get("releasenum") or badge_json[0].get("releaseNum") or 0)
        except Exception:
            rel_num = None
        if rel_num is None or rel_num <= 0:
            proc = subprocess.run(
                [ugs_exe, "ccd", "releases", "list",
                 "-p", project_id, "-e", env_name, "-b", "client-resources",
                 "--json", "--per-page", "1", "--page", "1"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                write_to_console("[CCD DOWNLOAD]", None, text_widget,
                                 f"[✗] Could not resolve release (badge={badge_name}). {proc.stderr.strip()}")
                return
            rel_list = json.loads(proc.stdout.strip())
            if isinstance(rel_list, dict) and "results" in rel_list:
                rel_list = rel_list["results"]
            if not rel_list:
                write_to_console("[CCD DOWNLOAD]", None, text_widget, "[✗] No releases found.")
                return
            rel_num = int(rel_list[0].get("ReleaseNum") or rel_list[0].get("releaseNum") or 0)
            rel_id  = rel_list[0].get("ReleaseId") or rel_list[0].get("releaseId")
        write_to_console("[CCD DOWNLOAD]", None, text_widget, f"[→] Using release #{rel_num}")
        if not rel_id:
            proc = subprocess.run(
                [ugs_exe, "ccd", "releases", "info", str(rel_num),
                 "-p", project_id, "-e", env_name, "-b", "client-resources", "--json"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            if proc.returncode != 0 or not proc.stdout.strip():
                write_to_console("[CCD DOWNLOAD]", None, text_widget,
                                 f"[✗] Could not inspect release {rel_num}: {proc.stderr.strip()}")
                return
            info = json.loads(proc.stdout.strip())
            rel_id = info.get("ReleaseId") or info.get("releaseId") or info.get("id")
            if not rel_id:
                write_to_console("[CCD DOWNLOAD]", None, text_widget, "[✗] Missing ReleaseId in CLI JSON.")
                return
        p = (entrie_name or "").strip().lower()
        if p in ("android", "ios", "both", ""):
            prefixes = {
                "android": ("android/",),
                "ios": ("ios/",),
                "both": ("android/", "ios/"),
                "": ("android/", "ios/"),
            }[p]
        else:
            prefixes = ((p + "/") if not p.endswith("/") else p,)

        def _match_prefix(path: str) -> bool:
            low = (path or "").lower()
            return any(low.startswith(px) for px in [px.lower() if px.endswith("/") else (px.lower()+"/") for px in prefixes])
        def _match_ext(path: str) -> bool:
            if not exts: return True
            low = (path or "").lower()
            return any(low.endswith(e.lower()) for e in exts)
        host = "https://services.api.unity.com"
        dest_root = os.path.join(output_dir, entrie_name)
        Path(dest_root).mkdir(parents=True, exist_ok=True)
        def _iter_entries():
            page = 1
            while True:
                url = (f"{host}/ccd/management/v1/projects/{project_id}/environments/{current_env}/"
                       f"buckets/{bucket_id}/releases/{rel_id}/entries")
                r = requests.get(url, headers=headers, params={"per_page": 200, "page": page}, timeout=(15,120))
                if r.status_code != 200:
                    write_to_console("[CCD DOWNLOAD]", None, text_widget,
                                     f"[✗] list page {page}: {r.status_code} {r.text[:200]}")
                    break
                data = r.json()
                items = data if isinstance(data, list) else data.get("results", [])
                if not items: break
                for it in items: yield it
                page += 1
        downloaded = skipped = failed = 0
        for it in _iter_entries():
            path = it.get("path") or ""
            if not path or not _match_prefix(path) or not _match_ext(path):
                continue
            size = it.get("content_size")
            out_path = os.path.join(dest_root, path)
            Path(os.path.dirname(out_path)).mkdir(parents=True, exist_ok=True)
            if os.path.exists(out_path):
                try:
                    if size is None or os.path.getsize(out_path) == int(size):
                        skipped += 1
                        write_to_console("[CCD DOWNLOAD]", None, text_widget, f"skip (up-to-date): {path}")
                        continue
                except Exception:
                    pass
            try:
                content_url = (f"{host}/ccd/management/v1/projects/{project_id}/environments/{current_env}/"
                               f"buckets/{bucket_id}/releases/{rel_id}/entry_by_path/content")
                with requests.get(content_url, headers=headers, params={"path": path}, stream=True, timeout=(15,300)) as r:
                    r.raise_for_status()
                    with open(out_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=256 * 1024):
                            if chunk: f.write(chunk)
                downloaded += 1
                write_to_console(f"[CCD DOWNLOAD] {path}", None, text_widget, "ok")
            except Exception as ex:
                failed += 1
                write_to_console("[CCD DOWNLOAD]", None, text_widget, f"fail: {path} → {ex}")
        write_to_console("[CCD DOWNLOAD]", None, text_widget,
                         f"[✓] Done env={env_name} release={rel_num} → {dest_root} | "
                         f"Downloaded={downloaded}, Failed={failed}, Skipped={skipped}")
    except Exception as e:
        write_to_console("[CCD DOWNLOAD]", None, text_widget, f"[EXCEPTION] {e}")
# Snapshot Unity CCD - END
#----------------------------------------------------------------
# Log Strip - START
DEBUG_CALL = (
    r'(?:UnityEngine\.)?Debug\.(?:Log|LogWarning|LogError|Assert)\s*'
    r'\('
    r'(?:[^()"\\]|"(?:\\.|[^"\\])*"|\\.|\(.*?\))*'
    r'\)'
    r'(?:\s*\+\s*(?:"(?:\\.|[^"\\])*"|@?"(?:\\.|[^"\\])*"|[A-Za-z0-9_\.]+))*'
)

SINGLE_IF_DEBUG = re.compile(
    rf'^(?P<indent>\s*)if\s*\((?P<cond>[^\)]*)\)\s*{DEBUG_CALL}\s*;?\s*$',
    re.MULTILINE
)

SINGLE_ELSE_DEBUG = re.compile(
    rf'^(?P<indent>\s*)else\s*(?!if)\s*{DEBUG_CALL}\s*;?\s*$',
    re.MULTILINE
)

BLOCK_ONLY_DEBUG = re.compile(
    rf'\{{\s*{DEBUG_CALL}\s*;?\s*\}}',
    re.MULTILINE
)

STANDALONE_DEBUG_LINE = re.compile(
    rf'^\s*{DEBUG_CALL}\s*;?\s*$',
    re.MULTILINE
)

LINE_COMMENT = re.compile(r'^\s*//.*$', re.MULTILINE)
BLOCK_COMMENT_STANDALONE = re.compile(r'^[ \t]*/\*[\s\S]*?\*/[ \t]*$', re.MULTILINE)
_LINE_COMMENT_ANY = re.compile(r'^\s*//.*$', re.MULTILINE)
_BLOCK_COMMENT_ANY = re.compile(r'/\*[\s\S]*?\*/', re.DOTALL)

TRY_BLOCK = re.compile(
    r'try\s*\{.*?\}(?:\s*catch\s*\(.*?\)\s*\{.*?\})*(?:\s*finally\s*\{.*?\})?',
    re.DOTALL | re.MULTILINE
)

def _protect_try_blocks(text: str):
    protected = {}
    def repl(m):
        key = f"__TRY_BLOCK_{len(protected)}__"
        protected[key] = m.group(0)
        return key
    return TRY_BLOCK.sub(repl, text), protected

def _restore_try_blocks(text: str, protected: dict):
    for k, v in protected.items():
        text = text.replace(k, v)
    return text

def _strip_comments(s: str) -> str:
    s = _BLOCK_COMMENT_ANY.sub('', s)
    s = _LINE_COMMENT_ANY.sub('', s)
    return s

def _strip_debug_calls(s: str) -> str:
    pattern = re.compile(
        r'(?P<pre>^[^\S\n]*)'
        r'(?:UnityEngine\.)?Debug\.(?:Log|LogWarning|LogError|Assert)\s*\('
        r'(?:[^()"\\]|"(?:\\.|[^"\\])*"|\\.|\(.*?\))*'
        r'\)'
        r'(?:\s*\+\s*(?:"(?:\\.|[^"\\])*"|@?"(?:\\.|[^"\\])*"|[A-Za-z0-9_\.]+))*'
        r'\s*;?',
        flags=re.MULTILINE | re.DOTALL
    )
    result = pattern.sub(lambda m: m.group('pre'), s)
    result = re.sub(r'^[ \t]*(\+|\$)?@?"[^"]*"\s*;?\s*$', '', result, flags=re.MULTILINE)
    result = re.sub(r'^[ \t]*\+\s*[A-Za-z0-9_\.]+\s*;?\s*$', '', result, flags=re.MULTILINE)
    return result

def _next_nonempty(lines, idx):
    j = idx
    while j < len(lines) and lines[j].strip() == '':
        j += 1
    return j

def _grab_stmt_or_block(lines, start_idx):
    if start_idx >= len(lines):
        return [], start_idx, False
    first = lines[start_idx]
    if first.strip().startswith('{'):
        depth = 0
        j = start_idx
        while j < len(lines):
            t = lines[j]
            depth += t.count('{')
            depth -= t.count('}')
            if depth == 0:
                return lines[start_idx+1:j], j+1, True
            j += 1
        return lines[start_idx+1:j], j, True
    else:
        return [first], start_idx + 1, False

def _is_debug_only(body_lines: list[str]) -> bool:
    if not body_lines:
        return True
    body = '\n'.join(body_lines)
    body = _strip_comments(body)
    body = _strip_debug_calls(body)
    return body.strip() == ''

def _invert_cond(cond: str) -> str:
    return f'!({cond.strip()})'

def fold_debug_only_if_else(text: str) -> str:
    lines = text.splitlines()
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m_if = re.match(r'^(\s*)if\s*\((.*?)\)\s*$', line)
        m_if_inline = re.match(
            r'^(\s*)if\s*\((.*?)\)\s*(?:\{)?\s*(?:UnityEngine\.)?Debug\.(?:Log|LogWarning|LogError|Assert)\s*\(.*?\)\s*;?\s*(?:\})?\s*$',
            line
        )
        if m_if or m_if_inline:
            indent = m_if.group(1) if m_if else m_if_inline.group(1)
            cond   = m_if.group(2) if m_if else m_if_inline.group(2)
            j = i + 1 if m_if else i + 1
            j = _next_nonempty(lines, j)
            if_body, after_if, _ = _grab_stmt_or_block(lines, j)
            k = _next_nonempty(lines, after_if)
            has_else = (k < len(lines) and re.match(r'^\s*else\b', lines[k]) is not None)
            if has_else and re.match(r'^\s*else\s+if\b', lines[k]):
                out.extend(lines[i:k+1])
                i = k + 1
                continue
            else_body = []
            after_else = k
            if has_else:
                else_line = lines[k]
                if '{' in else_line and else_line.strip().endswith('{'):
                    body_start = k
                else:
                    body_start = _next_nonempty(lines, k + 1)
                else_body, after_else, _ = _grab_stmt_or_block(lines, body_start)
            if_only_logs  = _is_debug_only(if_body)
            else_only_logs = _is_debug_only(else_body) if has_else else False
            if if_only_logs and has_else and not else_only_logs:
                out.append(f"{indent}if ({_invert_cond(cond)}) {{")
                if else_body:
                    out.extend(else_body)
                out.append(f"{indent}}}")
                i = after_else
                continue
            if if_only_logs and not has_else:
                i = after_if
                continue
            if has_else and else_only_logs:
                out.extend(lines[i:after_if])
                i = after_else
                continue
            end = after_else if has_else else after_if
            out.extend(lines[i:end])
            i = end
            continue
        out.append(line)
        i += 1
    return "\n".join(out)

def _fix_brace_balance(code: str) -> str:
    open_count = 0
    out = []
    for line in code.splitlines():
        open_count += line.count('{')
        open_count -= line.count('}')
        out.append(line)
    while open_count > 0:
        out.append('}')
        open_count -= 1
    return '\n'.join(out)

PREPROC_BLOCK = re.compile(r'#if[\s\S]*?#endif', re.MULTILINE)
def _protect_preproc_blocks(text):
    protected = {}
    def repl(m):
        key = f"__PREPROC_{len(protected)}__"
        protected[key] = m.group(0)
        return key
    return PREPROC_BLOCK.sub(repl, text), protected

def _restore_preproc_blocks(text, protected):
    for k, v in protected.items():
        text = text.replace(k, v)
    return text

def preserve_if_else_structure(text: str) -> str:
    lines = text.splitlines()
    output = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m_if = re.match(r'^(\s*)if\s*\((.*?)\)\s*$', line)
        if m_if:
            indent, cond = m_if.groups()
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j < len(lines) and lines[j].strip() == "{":
                k = j + 1
                depth = 1
                has_debug = False
                has_non_debug = False
                end = k
                while k < len(lines) and depth > 0:
                    t = lines[k]
                    ts = t.strip()
                    if "{" in t: depth += t.count("{")
                    if "}" in t:
                        depth -= t.count("}")
                        if depth == 0:
                            end = k
                            break
                    if ts and not ts.startswith("//"):
                        if re.search(r'(?:UnityEngine\.)?Debug\.(?:Log|LogWarning|LogError|Assert)\s*\(', ts):
                            has_debug = True
                        else:
                            has_non_debug = True
                    k += 1
                if has_debug and not has_non_debug:
                    output.append(f"{indent}if ({cond}) {{ }}")
                    i = end + 1
                    continue
            if j < len(lines) and re.search(r'Debug\.(Log|LogWarning|LogError|Assert)', lines[j]):
                j += 1
                while j < len(lines) and lines[j].strip() == "":
                    j += 1
                if j < len(lines) and lines[j].strip().startswith("else"):
                    output.append(f"{indent}if ({cond}) {{ }}")
                    i = j
                    continue
                else:
                    output.append(f"{indent}if ({cond}) {{ }}")
                    i = j
                    continue
        m_inline = re.match(r'^(\s*)if\s*\((.*?)\)\s*(?:UnityEngine\.)?Debug\.(Log|LogWarning|LogError|Assert)\(.*\)\s*;?\s*$', line)
        if m_inline:
            indent, cond, _ = m_inline.groups()
            output.append(f"{indent}if ({cond}) {{ }}")
            i += 1
            continue
        m_else = re.match(r'^(\s*)else\s*(?:UnityEngine\.)?Debug\.(Log|LogWarning|LogError|Assert)\(.*\)\s*;?\s*$', line)
        if m_else:
            indent = m_else.group(1)
            output.append(f"{indent}else {{ }}")
            i += 1
            continue
        output.append(line)
        i += 1
    return "\n".join(output)

def strip_line_start_debug_calls_balanced(text: str) -> str:
    out, last = [], 0
    pattern = re.compile(r'^(?P<indent>\s*)(?P<prefix>(?:UnityEngine\.)?Debug\.(?:Log|LogWarning|LogError|Assert))\s*\(',re.MULTILINE)
    for m in pattern.finditer(text):
        start = m.start()
        out.append(text[last:start])
        depth = 0
        i = m.end() - 1
        n = len(text)
        in_str, esc = False, False
        while i < n:
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == '(':
                    depth += 1
                elif ch == ')':
                    depth -= 1
                    if depth == 0:
                        while i < n and text[i] not in ';\n':
                            i += 1
                        if i < n and text[i] == ';':
                            i += 1
                        while i < n and text[i] in ' \t\r\n':
                            i += 1
                        break
            i += 1
        last = i
        while i < n:
            if text[i:].lstrip().startswith('+'):
                i += 1
                while i < n and text[i] not in ';\n':
                    i += 1
                if i < n and text[i] == ';':
                    i += 1
                continue
            break
    out.append(text[last:])
    return ''.join(out)

def _normalize_if_else_braces(text):
    lines = text.splitlines()
    out = []
    total = len(lines)
    i = 0
    while i < total:
        line = lines[i]
        stripped = line.strip()
        m_if = re.match(r'^(\s*)if\s*\((.*?)\)\s*$', line)
        m_else = re.match(r'^(\s*)else\s*$', line)
        if m_if:
            indent = m_if.group(1)
            cond = m_if.group(2).strip()
            j = i + 1
            while j < total and lines[j].strip() == '':
                j += 1
            if j >= total:
                out.append(f"{indent}if ({cond}) {{ }}")
                i += 1
                continue
            next_line = lines[j].strip()
            if next_line.startswith('{') or next_line.startswith('else') or next_line.startswith('}'):
                out.append(line)
                i += 1
                continue
            if not re.match(r'^(//|/\*|\*|\}|#|$)', next_line):
                out.append(line)
                i += 1
                continue
            out.append(f"{indent}if ({cond}) {{ }}")
            i += 1
            continue
        if m_else:
            indent = m_else.group(1)
            j = i + 1
            while j < total and lines[j].strip() == '':
                j += 1
            if j >= total:
                out.append(f"{indent}else {{ }}")
                i += 1
                continue
            next_line = lines[j].strip()
            if next_line.startswith('{') or next_line.startswith('if') or next_line.startswith('}'):
                out.append(line)
                i += 1
                continue
            if not re.match(r'^(//|/\*|\*|\}|#|$)', next_line):
                out.append(line)
                i += 1
                continue
            out.append(f"{indent}else {{ }}")
            i += 1
            continue
        out.append(line)
        i += 1
    return "\n".join(out)

def log_strip(text_widget, project_path):
    ASSETS_PATH = os.path.join(project_path, "Assets")
    BACKUP_PATH = os.path.join(project_path, "Backup_DebugLogs")
    IGNORE_LIST = ["ScriptingBuilderHelpers.cs"]
    def should_ignore(p: str) -> bool:
        p = p.lower().replace("\\", "/")
        return any(x.lower() in p for x in IGNORE_LIST)
    os.makedirs(BACKUP_PATH, exist_ok=True)
    modified = []
    for root, _, files in os.walk(ASSETS_PATH):
        for fname in files:
            if not fname.endswith(".cs"):
                continue
            path = os.path.join(root, fname)
            if should_ignore(path):
                continue
            with open(path, "r", encoding="utf-8") as f:
                src = f.read()
            text, prot_preproc = _protect_preproc_blocks(src)
            text, prot_try = _protect_try_blocks(text)
            text = _strip_debug_calls(text)
            text = fold_debug_only_if_else(text)
            text = preserve_if_else_structure(text)
            text = strip_line_start_debug_calls_balanced(text)
            text = STANDALONE_DEBUG_LINE.sub("", text)
            text = SINGLE_IF_DEBUG.sub(lambda m: f"{m.group('indent')}if ({m.group('cond')}) {{ }}", text)
            text = SINGLE_ELSE_DEBUG.sub(lambda m: f"{m.group('indent')}else {{ }}", text)
            text = BLOCK_ONLY_DEBUG.sub("{ }", text)
            text = BLOCK_COMMENT_STANDALONE.sub("", text)
            text = LINE_COMMENT.sub("", text)
            text = re.sub(r'\n{3,}', '\n\n', text)
            text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
            text = _restore_try_blocks(text, prot_try)
            text = _restore_preproc_blocks(text, prot_preproc)
            text = re.sub(r'^\s*\$\s*".*?"\s*;?\s*$', '', text, flags=re.MULTILINE)
            text = re.sub(r'^\s*\+\s*".*?"\s*;?\s*$', '', text, flags=re.MULTILINE)
            text = re.sub(r'^[ \t]*(?:\+|\$)?@?"[^"]*"\s*;?\s*$', '', text, flags=re.MULTILINE)
            text = _normalize_if_else_braces(text)
            text = _fix_brace_balance(text)
            if text != src:
                backup = os.path.join(BACKUP_PATH, os.path.relpath(path, project_path))
                os.makedirs(os.path.dirname(backup), exist_ok=True)
                shutil.copy2(path, backup)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(text)
                modified.append(path)
    write_to_console("[STRIPPING]", None, text_widget, f"Stripped Debug calls safely from {len(modified)} files (structure preserved).")
    if modified:
        write_to_console("[STRIPPING]", None, text_widget, f"Backup saved in: {BACKUP_PATH}")
# Log Strip - END
#----------------------------------------------------------------
# Force reimport and recompile - START
def trigger_recompile(text_widget, unity_path, project_path):
    write_to_console("[RECOMPILE]", None, text_widget, "Executing Unity reimport and recompile...")
    cmd = [
        unity_path,
        "-batchmode",
        "-quit",
        "-projectPath", project_path,
        "-executeMethod", "EditorApplication.Exit",
        "-logFile", "-"
    ]
    subprocess.run(cmd, check=False)
    write_to_console("[RECOMPILE]", None, text_widget, "Unity reimport and recompile triggered")
# Force reimport and recompile - END
#----------------------------------------------------------------
# Purger - START
def purge_folder(text_widget):
    subdirs = ["Android/dev", "Android/production", "Android/qa", "Android/staging", "iOS/dev", "iOS/production", "iOS/qa", "iOS/staging"]
    for sub in subdirs:
        folder = os.path.join("Users/dreamteamadmin/Projects/builds", sub)
        if not os.path.exists(folder):
            return
        for entry in os.listdir(folder):
            full_path = os.path.join(folder, entry)
            try:
                if os.path.isfile(full_path) or os.path.islink(full_path):
                    os.unlink(full_path)
                elif os.path.isdir(full_path):
                    shutil.rmtree(full_path)
            except Exception as e:
                write_to_console("[PURGE]", None, text_widget, f"{full_path}: {e}")
# Purger - END
#----------------------------------------------------------------
# Storing Build - START
def copy_build_folder_to_network(text_widget, src_folder, environment):
    platforms = ["Android", "iOS"]
    for platform in platforms:
        dest_folder = os.path.join(r"smb://192.168.130.200/Dream Team/Machine/Build_Records",platform,environment)
        os.makedirs(dest_folder, exist_ok=True)
        write_to_console("[STORAGE]", None, text_widget, f"Copying build folder from:\n  {src_folder}\nTo:\n  {dest_folder}")
        for root, dirs, files in os.walk(src_folder):
            rel_path = os.path.relpath(root, src_folder)
            dest_path = os.path.join(dest_folder, rel_path)
            os.makedirs(dest_path, exist_ok=True)
            for file in files:
                src_file = os.path.join(root, file)
                dest_file = os.path.join(dest_path, file)
                shutil.copy2(src_file, dest_file)
        write_to_console("[STORAGE]", None, text_widget, f"Folder copied successfully to {dest_folder}")
# Storing Build - END
#----------------------------------------------------------------
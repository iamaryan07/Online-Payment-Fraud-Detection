# lib/device_fingerprint.py - Device fingerprinting simulation
import hashlib
import json
import random
from datetime import datetime

class DeviceFingerprint:
    def __init__(self):
        self.known_devices = {}  # Store device fingerprints
    
    def generate_fingerprint(self, user_agent, screen_res, timezone, language, ip):
        """Generate device fingerprint from browser data"""
        device_data = {
            "user_agent": user_agent,
            "screen_resolution": screen_res,
            "timezone": timezone,
            "language": language,
            "ip_hash": hashlib.md5(ip.encode()).hexdigest()[:8]
        }
        
        fingerprint = hashlib.sha256(json.dumps(device_data, sort_keys=True).encode()).hexdigest()
        return fingerprint, device_data
    
    def assess_device_risk(self, fingerprint, device_data, user_id):
        """Assess risk based on device characteristics"""
        risk_score = 0.0
        risk_factors = []
        
        # Check if device is known for this user
        user_devices = self.known_devices.get(user_id, set())
        if fingerprint not in user_devices:
            risk_score += 0.3
            risk_factors.append("New device")
        
        # Check for risky characteristics
        if "mobile" not in device_data["user_agent"].lower():
            risk_score += 0.1
            risk_factors.append("Desktop device")
        
        if "unknown" in device_data["timezone"].lower():
            risk_score += 0.2
            risk_factors.append("Unknown timezone")
        
        # Suspicious screen resolutions (common for emulators)
        suspicious_resolutions = ["800x600", "1024x768", "320x240"]
        if device_data["screen_resolution"] in suspicious_resolutions:
            risk_score += 0.4
            risk_factors.append("Suspicious screen resolution")
        
        # Store device for future reference
        if user_id not in self.known_devices:
            self.known_devices[user_id] = set()
        self.known_devices[user_id].add(fingerprint)
        
        return min(risk_score, 1.0), risk_factors

def generate_realistic_device_data():
    """Generate realistic device data for simulation"""
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X)",
        "Mozilla/5.0 (Android 11; Mobile; rv:68.0) Gecko/68.0 Firefox/88.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    ]
    
    resolutions = ["1920x1080", "1366x768", "375x667", "414x896", "1536x864"]
    timezones = ["America/New_York", "Europe/London", "Asia/Tokyo", "UTC"]
    languages = ["en-US", "en-GB", "es-ES", "fr-FR", "de-DE"]
    
    return {
        "user_agent": random.choice(user_agents),
        "screen_resolution": random.choice(resolutions),
        "timezone": random.choice(timezones),
        "language": random.choice(languages)
    }

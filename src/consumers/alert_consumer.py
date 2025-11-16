"""
Simple consumer for cryptocurrency price alerts from Flink anomaly detection.

Subscribes to 'crypto-alerts' Kafka topic and displays formatted alerts.
Run this alongside the Flink job to monitor anomalies in real-time.

Author: Zaid
Phase 3 - Week 6
"""

import json
import sys
import os
from datetime import datetime
from kafka import KafkaConsumer
from kafka.errors import KafkaError

# ROOT CAUSE FIX: Add src directory to Python path
# This works regardless of where script is run from
script_dir = os.path.dirname(os.path.abspath(__file__))  # src/consumers/
src_dir = os.path.dirname(script_dir)  # src/
project_root = os.path.dirname(src_dir)  # project root

# Add src to path so we can import config
sys.path.insert(0, src_dir)

# Now import config (should work from any directory)
from config import (
    KAFKA_BOOTSTRAP_SERVERS,
    KAFKA_SECURITY_PROTOCOL
)


class AlertConsumer:
    """Consumer for crypto price alerts"""
    
    def __init__(self):
        self.consumer = None
        self.alerts_received = 0
        
    def connect(self):
        """Connect to Kafka and subscribe to alerts topic"""
        try:
            self.consumer = KafkaConsumer(
                'crypto-alerts',
                bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
                security_protocol=KAFKA_SECURITY_PROTOCOL,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',  # Only new alerts
                group_id='alert-monitor',
                enable_auto_commit=True
            )
            print("✅ Connected to Kafka - Monitoring crypto-alerts topic...")
            print("=" * 80)
            print()
            return True
            
        except KafkaError as e:
            print(f"❌ Kafka connection error: {e}")
            return False
    
    def format_alert(self, alert):
        """Format alert for console display"""
        symbol = alert.get('symbol', 'UNKNOWN')
        alert_type = alert.get('alert_type', 'UNKNOWN')
        change = alert.get('price_change_percent', 0)
        open_price = alert.get('open_price', 0)
        close_price = alert.get('close_price', 0)
        severity = alert.get('severity', 'LOW')
        window_start = alert.get('window_start', '')
        
        # Emoji based on severity
        emoji = "🔥" if severity == "HIGH" else "⚠️" if severity == "MEDIUM" else "📊"
        
        # Color based on spike/drop
        direction = "📈 SPIKE" if alert_type == "PRICE_SPIKE" else "📉 DROP"
        
        print(f"{emoji} {severity} ALERT - {symbol} {direction}")
        print(f"   Change: {change:.2f}%")
        print(f"   Open: ${open_price:,.2f} → Close: ${close_price:,.2f}")
        print(f"   Window: {window_start}")
        print(f"   Timestamp: {alert.get('timestamp', '')}")
        print("-" * 80)
        print()
    
    def consume(self):
        """Consume and display alerts"""
        if not self.consumer:
            print("❌ Not connected to Kafka")
            return
        
        try:
            print("👀 Waiting for alerts... (Press Ctrl+C to stop)")
            print("   Anomaly threshold: >5% price change in 1-minute window")
            print("=" * 80)
            print()
            
            for message in self.consumer:
                self.alerts_received += 1
                alert = message.value
                
                print(f"Alert #{self.alerts_received} received at {datetime.now().strftime('%H:%M:%S')}")
                self.format_alert(alert)
                
        except KeyboardInterrupt:
            print("\n⏹️  Stopping alert consumer...")
            print(f"Total alerts received: {self.alerts_received}")
        except Exception as e:
            print(f"❌ Error consuming alerts: {e}")
        finally:
            if self.consumer:
                self.consumer.close()


def main():
    """Main entry point"""
    print()
    print("=" * 80)
    print("🚨 CRYPTOCURRENCY PRICE ALERT MONITOR")
    print("=" * 80)
    print()
    
    consumer = AlertConsumer()
    
    if consumer.connect():
        consumer.consume()
    else:
        print("❌ Failed to connect to Kafka")
        sys.exit(1)


if __name__ == "__main__":
    main()

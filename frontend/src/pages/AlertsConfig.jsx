import { useState, useCallback } from "react";
import axios from "axios";
import { API } from "../App";
import { Send, CheckCircle, AlertCircle } from "lucide-react";
import { toast } from "sonner";

export default function AlertsConfig() {
  const [telegramChatId, setTelegramChatId] = useState("");
  const [testingTelegram, setTestingTelegram] = useState(false);

  const testTelegram = useCallback(async () => {
    if (!telegramChatId) {
      toast.error("Please enter your Telegram Chat ID");
      return;
    }

    setTestingTelegram(true);
    try {
      const response = await axios.post(
        `${API}/alerts/test`,
        null,
        { params: { chat_id: telegramChatId } }
      );
      if (response.data.success) {
        toast.success("Test message sent! Check your Telegram");
      } else {
        toast.error("Failed to send test message");
      }
    } catch (error) {
      toast.error(
        error.response?.data?.detail || "Telegram not configured on server"
      );
    } finally {
      setTestingTelegram(false);
    }
  }, [telegramChatId]);

  return (
    <div className="page-container" data-testid="alerts-page">
      <div className="page-header">
        <h1 className="page-title">Alert Configuration</h1>
        <p className="page-subtitle">
          Test Telegram alerts for arbitrage opportunities
        </p>
      </div>

      <div className="max-w-lg mx-auto">
        {/* Telegram Setup */}
        <div className="card" data-testid="telegram-setup">
          <div className="card-header">
            <span className="card-title">Telegram Setup</span>
            <Send className="w-4 h-4 text-blue-500" />
          </div>

          <div className="space-y-4">
            <div className="p-4 bg-zinc-900 rounded-lg">
              <h4 className="font-medium mb-2">How to get your Chat ID:</h4>
              <ol className="text-sm text-zinc-400 list-decimal list-inside space-y-1">
                <li>Open Telegram and search for @userinfobot</li>
                <li>Start the bot and it will show your Chat ID</li>
                <li>Copy the number and paste it below</li>
              </ol>
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Your Telegram Chat ID
              </label>
              <input
                type="text"
                className="input"
                placeholder="e.g., 123456789"
                value={telegramChatId}
                onChange={(e) => setTelegramChatId(e.target.value)}
                data-testid="telegram-chat-id"
              />
            </div>

            <button
              onClick={testTelegram}
              className="btn btn-primary w-full flex items-center justify-center gap-2"
              disabled={testingTelegram}
              data-testid="test-telegram-btn"
            >
              {testingTelegram ? (
                <span className="animate-spin">⏳</span>
              ) : (
                <Send className="w-4 h-4" />
              )}
              Send Test Alert
            </button>

            <div className="p-3 bg-yellow-900/10 border border-yellow-900/30 rounded-lg">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-yellow-500 mt-0.5" />
                <p className="text-xs text-zinc-400">
                  Note: Telegram alerts require the server to have a Telegram Bot
                  Token configured. Contact your admin if test alerts don't work.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Info Box */}
        <div className="card mt-6 bg-blue-900/10 border-blue-900/30">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-blue-500 mt-0.5" />
            <div>
              <h3 className="font-medium text-blue-500 mb-1">Alert Triggers</h3>
              <ul className="text-sm text-zinc-400 list-disc list-inside space-y-1">
                <li><strong>Cross-Exchange:</strong> When NSE vs BSE spread exceeds threshold</li>
                <li><strong>Cash & Carry:</strong> When basis exceeds threshold</li>
                <li><strong>Synthetic:</strong> When synthetic vs actual futures mispricing detected</li>
                <li><strong>Statistical:</strong> When Z-score exceeds ±2</li>
                <li><strong>Price:</strong> When stock moves more than threshold %</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

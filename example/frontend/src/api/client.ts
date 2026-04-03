/**
 * Home Assistant API Client
 */

import axios, { AxiosInstance } from "axios";

interface HAResponse<T = any> {
  success: boolean;
  data?: T;
  error?: string;
}

const isProd = import.meta.env.MODE === "production";

export const API_BASE_URL = isProd ? "api" : "http://localhost:8000/api";

export const WS_URL = isProd
  ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}${window.location.pathname.replace(/\/$/, "")}/ws`
  : "ws://localhost:8000/ws";

class HAClient {
  private client: AxiosInstance;
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      timeout: 10000,
    });
  }

  /**
   * Get current status
   */
  async getStatus() {
    try {
      const response = await this.client.get("/status");
      return response.data;
    } catch (error) {
      console.error("Failed to get status:", error);
      throw error;
    }
  }

  /**
   * Get list of Home Assistant entities
   */
  async getEntities() {
    try {
      const response = await this.client.get("/entities");
      return response.data;
    } catch (error) {
      console.error("Failed to get entities:", error);
      throw error;
    }
  }

  /**
   * Call a Home Assistant service
   */
  async callService(
    domain: string,
    service: string,
    data?: Record<string, any>,
  ): Promise<HAResponse> {
    try {
      const response = await this.client.post(
        `/service/${domain}/${service}`,
        data,
      );
      return response.data;
    } catch (error) {
      console.error(`Failed to call service ${domain}.${service}:`, error);
      throw error;
    }
  }

  /**
   * Connect to WebSocket for real-time updates
   */
  connect(onMessage: (data: any) => void, onError?: (error: Event) => void) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log("WebSocket already connected");
      return;
    }

    console.log("Connecting to WebSocket:", WS_URL);

    try {
      this.ws = new WebSocket(WS_URL);

      this.ws.onopen = () => {
        console.log("WebSocket connected");
        this.reconnectAttempts = 0;
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage(data);
        } catch (error) {
          console.error("Failed to parse WebSocket message:", error);
        }
      };

      this.ws.onerror = (error) => {
        console.error("WebSocket error:", error);
        if (onError) onError(error);
      };

      this.ws.onclose = () => {
        console.log("WebSocket disconnected");
        this.reconnect(onMessage, onError);
      };
    } catch (error) {
      console.error("Failed to connect WebSocket:", error);
      if (onError && error instanceof Event) onError(error);
    }
  }

  /**
   * Send message via WebSocket
   */
  send(data: any) {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      console.warn("WebSocket not connected");
      return;
    }

    this.ws.send(JSON.stringify(data));
  }

  /**
   * Disconnect WebSocket
   */
  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Reconnect with backoff
   */
  private reconnect(
    onMessage: (data: any) => void,
    onError?: (error: Event) => void,
  ) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("Max reconnection attempts reached");
      return;
    }

    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    console.log(
      `Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`,
    );

    this.reconnectAttempts++;

    setTimeout(() => {
      this.connect(onMessage, onError);
    }, delay);
  }
}

export default new HAClient();

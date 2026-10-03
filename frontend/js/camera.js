import { inspectCanvas } from "./quality.js";

/** Owns camera permission, capture, and real-time local quality preview. */
export class CameraController {
  /** @param {HTMLVideoElement} video @param {(quality: ReturnType<typeof inspectCanvas>) => void} onQuality */
  constructor(video, onQuality) {
    this.video = video;
    this.onQuality = onQuality;
    this.stream = null;
    this.timer = null;
  }

  async start() {
    if (!navigator.mediaDevices?.getUserMedia)
      throw new Error("Camera access is not available in this browser.");
    this.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: { ideal: "environment" }, width: { ideal: 1280 } },
      audio: false,
    });
    this.video.srcObject = this.stream;
    await this.video.play();
    this.loop();
  }

  loop() {
    if (!this.stream) return;
    this.onQuality(inspectCanvas(this.video));
    this.timer = window.setTimeout(() => this.loop(), 750);
  }

  async capture() {
    if (!this.video.videoWidth) throw new Error("Wait for the camera preview before taking a photo.");
    const canvas = document.createElement("canvas");
    canvas.width = this.video.videoWidth;
    canvas.height = this.video.videoHeight;
    canvas.getContext("2d").drawImage(this.video, 0, 0);
    return new Promise((resolve) => canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.94));
  }

  stop() {
    window.clearTimeout(this.timer);
    this.stream?.getTracks().forEach((track) => track.stop());
    this.stream = null;
    this.video.srcObject = null;
  }
}

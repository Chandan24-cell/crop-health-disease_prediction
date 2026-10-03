/** Estimate image framing quality in-browser using canvas Laplacian variance and luminance. */
/** @param {CanvasImageSource} source @param {number} [maxSide] */
export function inspectCanvas(source, maxSide = 240) {
  const width =
    source instanceof HTMLVideoElement
      ? source.videoWidth
      : source instanceof HTMLImageElement
        ? source.naturalWidth
        : source.width;
  const height =
    source instanceof HTMLVideoElement
      ? source.videoHeight
      : source instanceof HTMLImageElement
        ? source.naturalHeight
        : source.height;
  if (!width || !height)
    return { blur: 0, brightness: 0, resolution: [0, 0], issues: ["Waiting for camera"] };
  const scale = Math.min(1, maxSide / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(width * scale));
  canvas.height = Math.max(1, Math.round(height * scale));
  const context = canvas.getContext("2d", { willReadFrequently: true });
  context.drawImage(source, 0, 0, canvas.width, canvas.height);
  const { data } = context.getImageData(0, 0, canvas.width, canvas.height);
  const pixels = canvas.width * canvas.height;
  const gray = new Float32Array(pixels);
  let sum = 0;
  let leafToneCount = 0;
  let centerLeafToneCount = 0;
  const centerLeft = Math.floor(canvas.width * 0.16);
  const centerRight = Math.ceil(canvas.width * 0.84);
  const centerTop = Math.floor(canvas.height * 0.12);
  const centerBottom = Math.ceil(canvas.height * 0.88);
  const centerPixels = Math.max(1, (centerRight - centerLeft) * (centerBottom - centerTop));
  for (let i = 0, p = 0; i < data.length; i += 4, p += 1) {
    gray[p] = 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
    sum += gray[p];
    const red = data[i];
    const green = data[i + 1];
    const blue = data[i + 2];
    const likelyLeafTone = green > 45 && green > red * 0.82 && green > blue * 0.78;
    if (likelyLeafTone) {
      leafToneCount += 1;
      const x = p % canvas.width;
      const y = Math.floor(p / canvas.width);
      if (x >= centerLeft && x < centerRight && y >= centerTop && y < centerBottom) centerLeafToneCount += 1;
    }
  }
  const brightness = sum / pixels;
  const centeredLeafFill = centerLeafToneCount / centerPixels;
  let lapSum = 0;
  let lapSquareSum = 0;
  let count = 0;
  for (let y = 1; y < canvas.height - 1; y += 1) {
    for (let x = 1; x < canvas.width - 1; x += 1) {
      const p = y * canvas.width + x;
      const value = gray[p - canvas.width] + gray[p - 1] - 4 * gray[p] + gray[p + 1] + gray[p + canvas.width];
      lapSum += value;
      lapSquareSum += value * value;
      count += 1;
    }
  }
  const mean = count ? lapSum / count : 0;
  const blur = count ? Math.max(0, lapSquareSum / count - mean * mean) : 0;
  const issues = [];
  if (blur < 95) issues.push("Too blurry — hold still and tap to focus");
  if (brightness < 55) issues.push("Too dark — move into brighter light");
  if (brightness > 218) issues.push("Too bright — avoid direct glare");
  if (Math.min(width, height) < 220 || centeredLeafFill < 0.055 || leafToneCount / pixels < 0.025)
    issues.push("Move closer so the leaf fills the frame");
  return {
    blur: Math.round(blur),
    brightness: Math.round(brightness),
    resolution: [width, height],
    issues,
    centeredLeafFill: Number(centeredLeafFill.toFixed(3)),
  };
}

/** Rotate and center-crop an image before upload. @param {Blob} blob @param {number} rotation @param {number} zoom */
export async function prepareImage(blob, rotation = 0, zoom = 1) {
  const bitmap = await createImageBitmap(blob);
  const rotated = document.createElement("canvas");
  const quarterTurn = Math.abs(rotation % 180) === 90;
  rotated.width = quarterTurn ? bitmap.height : bitmap.width;
  rotated.height = quarterTurn ? bitmap.width : bitmap.height;
  const ctx = rotated.getContext("2d");
  ctx.translate(rotated.width / 2, rotated.height / 2);
  ctx.rotate((rotation * Math.PI) / 180);
  ctx.drawImage(bitmap, -bitmap.width / 2, -bitmap.height / 2);
  bitmap.close();
  const output = document.createElement("canvas");
  const maxSide = 2400;
  const scale = Math.min(1, maxSide / Math.max(rotated.width, rotated.height));
  output.width = Math.round(rotated.width * scale);
  output.height = Math.round(rotated.height * scale);
  const out = output.getContext("2d");
  const cropWidth = rotated.width / Math.max(1, zoom);
  const cropHeight = rotated.height / Math.max(1, zoom);
  out.drawImage(
    rotated,
    (rotated.width - cropWidth) / 2,
    (rotated.height - cropHeight) / 2,
    cropWidth,
    cropHeight,
    0,
    0,
    output.width,
    output.height,
  );
  return new Promise((resolve) => output.toBlob((value) => resolve(value || blob), "image/jpeg", 0.92));
}

/** @param {Blob} blob */
export function blobDataUrl(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

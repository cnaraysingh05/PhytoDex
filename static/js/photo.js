// Prepares a photo on the tablet before it is uploaded to the Pi.
// Shrinking it here makes uploads over Wi-Fi fast, keeps it under the
// backend's 10 MB analysis limit, and re-saves it as JPEG. Re-saving also
// drops the photo's hidden metadata, such as GPS location.

export class PhotoError extends Error {}

const MAX_SIDE = 2048;
const MAX_INPUT_BYTES = 40 * 1024 * 1024;
const UNREADABLE =
  "This photo couldn't be opened. Use a JPEG or PNG photo. On an iPhone or iPad, set Camera > Formats to Most Compatible.";

function loadWithImageElement(file) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => { URL.revokeObjectURL(url); resolve(image); };
    image.onerror = () => { URL.revokeObjectURL(url); reject(new Error("decode failed")); };
    image.src = url;
  });
}

async function decode(file) {
  if ("createImageBitmap" in window) {
    try {
      // "from-image" applies the camera's rotation so the plant isn't sideways.
      return await createImageBitmap(file, { imageOrientation: "from-image" });
    } catch {
      // Some browsers don't support the option; fall through.
    }
  }
  // <img> also applies the camera's rotation in current browsers.
  return loadWithImageElement(file);
}

export async function preparePhoto(file) {
  if (!file) throw new PhotoError("No photo was selected.");
  if (file.type && !file.type.startsWith("image/")) {
    throw new PhotoError("That file isn't a photo. Choose a JPEG or PNG image.");
  }
  if (file.size > MAX_INPUT_BYTES) {
    throw new PhotoError("That photo is too large (over 40 MB). Choose a smaller photo.");
  }

  let source;
  try {
    source = await decode(file);
  } catch {
    throw new PhotoError(UNREADABLE);
  }
  const width = source.width || source.naturalWidth;
  const height = source.height || source.naturalHeight;
  if (!width || !height) throw new PhotoError(UNREADABLE);

  const scale = Math.min(1, MAX_SIDE / Math.max(width, height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(width * scale);
  canvas.height = Math.round(height * scale);
  const context = canvas.getContext("2d");
  context.fillStyle = "#ffffff";  // transparent PNG areas become white, not black
  context.fillRect(0, 0, canvas.width, canvas.height);
  context.drawImage(source, 0, 0, canvas.width, canvas.height);
  if (typeof source.close === "function") source.close();

  const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
  if (!blob) throw new PhotoError(UNREADABLE);
  return { blob, filename: "scan.jpg", previewUrl: URL.createObjectURL(blob) };
}

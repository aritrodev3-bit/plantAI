from typing import Optional
import torch
import torch.nn.functional as F
import numpy as np
import cv2
from PIL import Image


class GradCAM:
    def __init__(self, model):
        self.model = model
        self.gradients: torch.Tensor | None = None
        self.activations: torch.Tensor | None = None

        # EfficientNet-B0: last conv block is model.features[-1]
        target_layer = model.features[-1]

        target_layer.register_forward_hook(self._save_activations)
        target_layer.register_full_backward_hook(self._save_gradients)

    def _save_activations(self, module, input, output):
        self.activations = output.detach()

    def _save_gradients(self, module, grad_input, grad_output):
        self.gradients = grad_output[0].detach()

    def generate(self, input_tensor: torch.Tensor, class_idx: Optional[int] = None):
        """
        input_tensor : (1, 3, 224, 224) — must NOT be inside torch.no_grad()
        Returns: (cam numpy array H×W, predicted class index)
        """
        self.model.eval()

        # Forward pass — gradients must flow, no torch.no_grad() here
        output = self.model(input_tensor)

        if class_idx is None:
            class_idx = output.argmax(dim=1).item()

        # Backward pass for the predicted class only
        self.model.zero_grad()
        one_hot = torch.zeros_like(output)
        one_hot[0][class_idx] = 1
        output.backward(gradient=one_hot)

        # Assert hooks fired — satisfies type checker and catches silent failures
        assert self.gradients is not None, "Gradients not captured — backward pass may have failed"
        assert self.activations is not None, "Activations not captured — forward pass may have failed"

        # GradCAM formula: weight activations by mean gradient
        weights = self.gradients.mean(dim=[2, 3], keepdim=True)
        cam = (weights * self.activations).sum(dim=1, keepdim=True)
        cam = F.relu(cam)
        cam_np = cam.squeeze().cpu().numpy()

        # Normalize to [0, 1]
        cam_np -= cam_np.min()
        if cam_np.max() != 0:
            cam_np /= cam_np.max()

        return cam_np, class_idx


def apply_heatmap(cam: np.ndarray, original_image: Image.Image, alpha: float = 0.45) -> Image.Image:
    """
    Overlay GradCAM heatmap on the original PIL image.
    Returns a PIL Image (RGB).
    """
    img_np = np.array(original_image.convert("RGB"))
    img_bgr = cv2.cvtColor(img_np, cv2.COLOR_RGB2BGR)

    # Resize CAM to match original image dimensions
    cam_resized = cv2.resize(cam, (img_bgr.shape[1], img_bgr.shape[0]))

    # Convert to uint8 numpy array explicitly — avoids cv2 type mismatch
    cam_uint8 = (255 * cam_resized).astype(np.uint8)
    heatmap = cv2.applyColorMap(cam_uint8, cv2.COLORMAP_JET)

    overlay = cv2.addWeighted(img_bgr, 1 - alpha, heatmap, alpha, 0)
    return Image.fromarray(cv2.cvtColor(overlay, cv2.COLOR_BGR2RGB))

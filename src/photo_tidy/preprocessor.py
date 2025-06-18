from abc import ABC, abstractmethod
from pathlib import Path
from datetime import datetime


class Preprocessor(ABC):
    """Base class for image preprocessors."""

    @abstractmethod
    def can_handle(self, image_path: Path) -> bool:
        """Check if this preprocessor can handle the given image.

        Args:
            image_path (Path): Path to the image file

        Returns:
            bool: True if this preprocessor can handle the image
        """
        pass

    @abstractmethod
    def process(self, image_path: Path) -> datetime:
        """Process the image and return its date.

        Args:
            image_path (Path): Path to the image file

        Returns:
            datetime: The date the photo was taken, or None if not found
        """
        pass

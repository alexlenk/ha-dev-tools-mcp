"""Compression handling for file downloads."""

import gzip
from typing import Tuple


class CompressionHandler:
    """Handles file compression and decompression."""
    
    @staticmethod
    async def compress(content: bytes) -> Tuple[bytes, float]:
        """
        Compress content using gzip.
        
        Args:
            content: Content to compress
            
        Returns:
            (compressed_content, compression_ratio) tuple
        """
        compressed = gzip.compress(content, compresslevel=6)
        ratio = 1.0 - (len(compressed) / len(content)) if len(content) > 0 else 0.0
        return compressed, ratio
    
    @staticmethod
    async def decompress(content: bytes) -> bytes:
        """
        Decompress gzip content.
        
        Args:
            content: Compressed content
            
        Returns:
            Decompressed content
        """
        return gzip.decompress(content)
    
    @staticmethod
    def should_compress(
        content: bytes,
        threshold: float = 0.10
    ) -> bool:
        """
        Determine if content should be compressed.
        
        Args:
            content: Content to evaluate
            threshold: Minimum compression ratio (default 10%)
            
        Returns:
            True if compression would be beneficial
        """
        if len(content) == 0:
            return False
        
        # Quick check: compress first 8KB to estimate ratio
        sample_size = min(8192, len(content))
        sample = content[:sample_size]
        compressed_sample = gzip.compress(sample, compresslevel=6)
        
        estimated_ratio = 1.0 - (len(compressed_sample) / len(sample))
        return estimated_ratio >= threshold

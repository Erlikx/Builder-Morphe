import logging
from rich.console import Console
from rich.logging import RichHandler

# GitHub Actions ve standart terminal ile tam uyumlu console nesnesi
console = Console(force_terminal=True)

def setup_logger(name: str = "Builder-Morphe", level: int = logging.INFO) -> logging.Logger:
    """Proje genelinde kullanılacak yapılandırılmış Rich Logger oluşturur."""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    if not logger.handlers:
        handler = RichHandler(
            console=console,
            rich_tracebacks=True,       # Hata durumunda ayrıntılı ve renkli stack trace
            tracebacks_show_locals=True, # Hatanın oluştuğu andaki local değişkenleri gösterir
            show_time=True,
            show_path=False
        )
        formatter = logging.Formatter("%(message)s", datefmt="[%X]")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger

log = setup_logger()

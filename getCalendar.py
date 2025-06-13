from exchangelib import Credentials, Account, Configuration, DELEGATE, EWSDateTime, EWSTimeZone
from cryptography.fernet import Fernet
from datetime import timedelta
import os
import json
from dotenv import load_dotenv
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

SERVER = os.environ.get("EXCHANGE_SERVER")


def get_credentials(credentials_file="credentials.enc"):
    """Retrieve and decrypt credentials from the encrypted file
    
    Args:
        credentials_file (str): Path to the encrypted credentials file
        
    Returns:
        tuple: Email and password from decrypted credentials
    """
    # 🔐 Charger la clé secrète depuis les variables d'environnement
    SECRET_KEY = os.environ.get("EXCHANGE_SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("EXCHANGE_SECRET_KEY n'est pas définie dans les variables d'environnement")

    fernet = Fernet(SECRET_KEY)

    # 🔓 Lire et déchiffrer les identifiants
    with open(credentials_file, "rb") as f:
        decrypted = fernet.decrypt(f.read())
        creds = json.loads(decrypted.decode())

    return creds["email"], creds["password"]

def get_exchange_account(email=None, password=None, server=SERVER, credentials_file="credentials.enc"):
    """Create and return an Exchange account object
    
    Args:
        email (str, optional): Email address. If None, will be loaded from credentials
        password (str, optional): Password. If None, will be loaded from credentials
        server (str): Exchange server address
        credentials_file (str): Path to credentials file if email/password not provided
        
    Returns:
        Account: Configured Exchange account object
    """
    if email is None or password is None:
        email, password = get_credentials(credentials_file)
    
    # Configuration Exchange locale
    config = Configuration(
        server=server,
        credentials=Credentials(email, password)
    )

    # Création de l'objet compte
    account = Account(
        primary_smtp_address=email,
        config=config,
        autodiscover=False,
        access_type=DELEGATE
    )
    
    return account

def retry_operation(operation, max_attempts=3, delay=5):
    """Retry an operation with exponential backoff
    
    Args:
        operation (callable): Function to retry
        max_attempts (int): Maximum number of retry attempts
        delay (int): Initial delay between retries in seconds
        
    Returns:
        Any: Result of the operation if successful
        
    Raises:
        Exception: The last exception encountered if all retries fail
    """
    attempt = 1
    last_exception = None
    
    while attempt <= max_attempts:
        try:
            return operation()
        except Exception as e:
            last_exception = e
            wait_time = delay * (2 ** (attempt - 1))
            logger.warning(f"Attempt {attempt} failed: {str(e)}. Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
            attempt += 1
    
    logger.error(f"All {max_attempts} attempts failed. Last error: {str(last_exception)}")
    raise last_exception

def get_calendar_events(account=None, start_date=None, end_date=None, days_ahead=7):
    """Retrieve calendar events for a specified period
    
    Args:
        account (Account, optional): Exchange account. If None, will be created
        start_date (EWSDateTime, optional): Start date. If None, will use current date
        end_date (EWSDateTime, optional): End date. If None, will use start_date + days_ahead
        days_ahead (int): Number of days to look ahead if end_date is None
        
    Returns:
        list: List of calendar events in the specified period
    """
    
    if account is None:
        account = get_exchange_account()
    
    # Fuseau horaire et période à analyser
    tz = EWSTimeZone('Europe/Paris')
    
    if start_date is None:
        start_date = EWSDateTime.now(tz)
    
    if end_date is None:
        end_date = start_date + timedelta(days=days_ahead)
    
    # Récupérer les événements avec mécanisme de retry
    def fetch_events():
        logger.info(f"Fetching calendar events from {start_date} to {end_date}")
        return list(account.calendar.view(start=start_date, end=end_date).order_by('start'))
    
    events = retry_operation(fetch_events)
    logger.info(f"Successfully retrieved {len(events)} calendar events")
    return events

def print_calendar_events(events):
    """Print calendar events in a readable format
    
    Args:
        events (list): List of calendar events
    """
    for item in events:
        print(f"{item.start} - {item.end} : {item.subject}")

def get_specific_period_events(start_year=2025, start_month=6, start_day=2, 
                               end_year=None, end_month=None, end_day=19):
    """Get events for a specific period across multiple months/years
    
    Args:
        start_year (int): Starting year
        start_month (int): Starting month
        start_day (int): Starting day
        end_year (int, optional): Ending year. If None, will use start_year
        end_month (int, optional): Ending month. If None, will use start_month
        end_day (int): Ending day
        
    Returns:
        list: List of calendar events in the specified period
    """
    # Set default end dates if not provided
    if end_year is None:
        end_year = start_year
    if end_month is None:
        end_month = start_month
    
    tz = EWSTimeZone('Europe/Paris')
    start = EWSDateTime(start_year, start_month, start_day, tzinfo=tz)
    end = EWSDateTime(end_year, end_month, end_day, tzinfo=tz)
    
    # Validate that end date is after start date
    if end < start:
        raise ValueError("End date must be after start date")
    
    return get_calendar_events(start_date=start, end_date=end)


if __name__ == "__main__":
    # Example usage when script is run directly
    events = get_specific_period_events(2025, 6, 2, end_day=19)
    print_calendar_events(events)
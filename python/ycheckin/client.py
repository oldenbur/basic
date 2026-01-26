import google.auth
import google.auth.transport.requests
import logging
import requests

from typing import Dict

SERVICE_URL = "https://ycheckin-304290747571.us-central1.run.app"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _adc_auth() -> Dict[str, str]:
    """
    Assume that GCP Application Default Credentials have been set up and return an http
    header that can be used to make authorized http calls.

    :return: An http request header with the ADC Bearer token populated.
    :rtype: Dict[str, str]
    """

    # Use the default credentials (ADC) and request an OIDC ID token
    credentials, project_id = google.auth.default()

    # The audience is typically the service URL itself
    # If the service requires a specific audience, specify it here
    audience = SERVICE_URL

    # Refresh the credentials to get an OIDC ID token
    # This automatically uses the credentials found by ADC
    auth_req = google.auth.transport.requests.Request()
    credentials.refresh(auth_req)

    # Get the ID token
    if not credentials.id_token:
        # For some credentials types, a specific OIDC token fetch is needed
        # Fallback using the more explicit way
        from google.oauth2 import id_token

        credentials.id_token = id_token.fetch_id_token(auth_req, audience)

    # Set the Authorization header with the ID token
    return {"Authorization": f"Bearer {credentials.id_token}"}


def main():
    logging.info("ycheckin.client() - starting")

    headers = _adc_auth()

    # Make the HTTP request
    response = requests.get(SERVICE_URL, headers=headers)

    # Check the response
    if response.status_code == 200:
        logging.info(f"Invocation successful: {response.text}")
    else:
        logging.error(
            f"Invocation failed with status code {response.status_code}: {response.text}"
        )


if __name__ == "__main__":
    main()

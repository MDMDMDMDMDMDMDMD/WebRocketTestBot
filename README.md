# WebRocketTestBot
# WebRocketTestBot

A Telegram bot integrated with Bitrix24 to manage "expired" leads. The bot notifies the manager about leads that have been in the "New" status for more than 2 hours and allows taking actions directly from Telegram.

## Features

-   **Bitrix24 Integration**: Fetches leads from CRM via Webhook.
-   **Lead Monitoring**: Identifies leads with status `NEW` created more than 2 hours ago.
-   **Telegram Notifications**: Sends a list of expired leads to the manager.
-   **Interactive Actions**:
    -   ✅ **Called**: Updates lead comment in Bitrix24 ("manager called").
    -   💬 **Wrote**: Updates lead comment in Bitrix24 ("manager wrote").
    -   ⏳ **Postpone**: Creates a task in Bitrix24 with a deadline of 2 hours.

## Prerequisites

-   Python 3.9+
-   A Bitrix24 account with permissions to create webhooks.
-   A Telegram Bot Token (from @BotFather).

## Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository_url>
    cd WebRocketTestBot
    ```

2.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    -   Copy `.env.example` to `.env`:
        ```bash
        cp .env.example .env
        ```
    -   Open `.env` and fill in the values:
        -   `TELEGRAM_TOKEN`: Your Telegram Bot Token.
        -   `BITRIX_WEBHOOK`: Your Bitrix24 Webhook URL (e.g., `https://your-domain.bitrix24.ru/rest/1/user_id/token/`). Ensure permissions for `crm` and `tasks` are enabled.
        -   `MANAGER_CHAT_ID`: The Telegram Chat ID of the manager who receives notifications.

## Usage

1.  **Start the bot**:
    ```bash
    python main.py
    ```

2.  **Bot Commands**:
    -   `/start`: Welcome message.
    -   `/leads`: Manually check for expired leads.
    -   `/help`: Show available commands.

3.  **Workflow**:
    -   The manager sends `/leads`.
    -   The bot fetches leads from Bitrix24 that are "New" and older than 2 hours.
    -   The bot sends a message for each lead with action buttons.
    -   The manager clicks a button to update the lead or create a follow-up task.

## Project Structure

-   `main.py`: Main bot logic and API integration.
-   `requirements.txt`: Python dependencies.
-   `.env.example`: Template for environment variables.


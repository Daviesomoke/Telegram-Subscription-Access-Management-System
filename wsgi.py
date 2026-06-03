from app import create_app

# gunicorn entry point - bot_app is None because the web service only serves the dashboard
# The bot polling runs separately in the Background Worker service
application = create_app(bot_app=None)

if __name__ == "__main__":
    application.run()

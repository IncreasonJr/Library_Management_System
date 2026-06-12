import click
from app import create_app

app = create_app()


@app.cli.command("send-reminders")
def send_reminders():
	"""Send due date and overdue email reminders."""
	from app.reminders import send_reminders_run
	send_reminders_run()
	click.echo("Completed sending reminders.")


if __name__ == "__main__":
	import sys
	if len(sys.argv) > 1:
		app.cli()
	else:
		app.run(debug=True)


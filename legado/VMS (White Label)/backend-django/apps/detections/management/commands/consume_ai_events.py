from django.core.management.base import BaseCommand
from apps.detections.consumer import EventConsumer


class Command(BaseCommand):
    help = 'Consume ai.events from RabbitMQ and save to database'

    def handle(self, *args, **options):
        self.stdout.write('Starting AI events consumer...')
        consumer = EventConsumer()
        consumer.consume()

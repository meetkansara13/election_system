"""
python manage.py seed_data
Seeds sample polling booths for Ahmedabad constituencies.
Replace with real ECI data from https://eci.gov.in/
"""
from django.core.management.base import BaseCommand
from apps.booth_locator.models import PollingBooth, Constituency


SAMPLE_BOOTHS = [
    # (booth_id, name, address, constituency, district, lat, lng, voters, accessible, cctv)
    ('AMD001', 'Maninagar Primary School', 'Maninagar, Ahmedabad', 'Maninagar', 'Ahmedabad', 22.9944, 72.6130, 1200, True, True),
    ('AMD002', 'Ellisbridge Govt School', 'Ellisbridge, Ahmedabad', 'Ellisbridge', 'Ahmedabad', 23.0225, 72.5714, 980, True, False),
    ('AMD003', 'Sabarmati Community Hall', 'Sabarmati, Ahmedabad', 'Sabarmati', 'Ahmedabad', 23.0783, 72.5938, 1450, False, True),
    ('AMD004', 'Vejalpur High School', 'Vejalpur, Ahmedabad', 'Vejalpur', 'Ahmedabad', 23.0020, 72.5070, 1100, True, True),
    ('AMD005', 'Nikol Public School', 'Nikol, Ahmedabad', 'Nikol', 'Ahmedabad', 23.0469, 72.6650, 1320, True, False),
    ('AMD006', 'Naroda Municipal School', 'Naroda, Ahmedabad', 'Naroda', 'Ahmedabad', 23.0780, 72.6560, 890, False, False),
    ('AMD007', 'Bapunagar School', 'Bapunagar, Ahmedabad', 'Bapunagar', 'Ahmedabad', 23.0570, 72.6270, 1050, True, True),
    ('AMD008', 'Amraiwadi Ward Office', 'Amraiwadi, Ahmedabad', 'Amraiwadi', 'Ahmedabad', 23.0130, 72.6420, 1300, True, False),
    ('AMD009', 'Dariapur Govt School', 'Dariapur, Ahmedabad', 'Dariapur', 'Ahmedabad', 23.0360, 72.5980, 770, True, True),
    ('AMD010', 'Jamalpur Community Centre', 'Jamalpur, Ahmedabad', 'Jamalpur', 'Ahmedabad', 23.0320, 72.6010, 850, False, False),
]

SAMPLE_CONSTITUENCIES = [
    ('Maninagar', 'Ahmedabad', 180000),
    ('Ellisbridge', 'Ahmedabad', 150000),
    ('Sabarmati', 'Ahmedabad', 210000),
    ('Vejalpur', 'Ahmedabad', 175000),
    ('Nikol', 'Ahmedabad', 190000),
    ('Naroda', 'Ahmedabad', 155000),
    ('Bapunagar', 'Ahmedabad', 165000),
    ('Amraiwadi', 'Ahmedabad', 185000),
    ('Dariapur', 'Ahmedabad', 120000),
    ('Jamalpur', 'Ahmedabad', 130000),
]


class Command(BaseCommand):
    help = 'Seed sample election data (booths + constituencies)'

    def handle(self, *args, **kwargs):
        # Constituencies
        for name, district, voters in SAMPLE_CONSTITUENCIES:
            Constituency.objects.update_or_create(
                name=name,
                defaults={'district': district, 'total_voters': voters}
            )
        self.stdout.write(self.style.SUCCESS(f'✓ {len(SAMPLE_CONSTITUENCIES)} constituencies seeded'))

        # Booths
        for row in SAMPLE_BOOTHS:
            bid, name, addr, const, dist, lat, lng, voters, acc, cctv = row
            PollingBooth.objects.update_or_create(
                booth_id=bid,
                defaults={
                    'name': name, 'address': addr, 'constituency': const,
                    'district': dist, 'latitude': lat, 'longitude': lng,
                    'total_voters': voters, 'is_accessible': acc, 'has_cctv': cctv,
                }
            )
        self.stdout.write(self.style.SUCCESS(f'✓ {len(SAMPLE_BOOTHS)} booths seeded'))
        self.stdout.write(self.style.WARNING('⚠  Replace with real ECI data: https://eci.gov.in/'))

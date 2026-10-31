import factory

from apps.accounts.models import NafathVerification, User
from apps.accounts.tests.factories import UserFactory
from apps.brokers.models import Agency, BrokerProfile


class VerifiedUserFactory(UserFactory):
    """A user who has passed Nafath verification."""

    class Meta:
        skip_postgeneration_save = True

    @factory.post_generation
    def nafath(self, create, extracted, **kwargs):
        if create:
            NafathVerification.objects.create(
                user=self,
                transaction_ref=f"test-{self.pk}",
                status=NafathVerification.Status.APPROVED,
            )


class BrokerProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = BrokerProfile

    user = factory.SubFactory(VerifiedUserFactory, role=User.Role.BROKER)
    name_ar = "وسيط تجريبي"
    name_en = factory.Sequence(lambda n: f"Test Broker {n}")
    fal_licence = factory.Sequence(lambda n: f"{1100000000 + n}")
    whatsapp = factory.Sequence(lambda n: f"+9665{n + 50000000:08d}")


class AgencyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Agency

    admin = factory.SubFactory(VerifiedUserFactory, role=User.Role.AGENCY_ADMIN)
    name_ar = "مكتب تجريبي"
    name_en = factory.Sequence(lambda n: f"Test Agency {n}")
    cr_number = factory.Sequence(lambda n: f"{2050000000 + n}")
    fal_licence = factory.Sequence(lambda n: f"{1200000000 + n}")

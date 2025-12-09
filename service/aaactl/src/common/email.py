import logging

from django.conf import settings
from django.core.mail.message import EmailMultiAlternatives

logger = logging.getLogger("django")

# TODO move to fullctl.django.mail


def email_noreply(address, subject, message, **kwargs):
    """
    Sends email to user from noreply address
    """
    email(settings.NO_REPLY_EMAIL, [address], subject, message, **kwargs)


def email_contact_us(replyto, subject, message, **kwargs):
    """
    Sends email to CONTACT_US_EMAIL with a reply-to header set
    """
    email(
        settings.DEFAULT_FROM_EMAIL,
        [settings.CONTACT_US_EMAIL],
        subject,
        message,
        reply_to=replyto,
        **kwargs,
    )


def email(sender, addresses, subject, message, reply_to=None, **kwargs):
    if reply_to:
        headers = {"Reply-To": reply_to}
    else:
        headers = {}

    for address in addresses:
        # TODO: this is deprecated and can be removed
        # dev instances use console backend anyhow
        if settings.DEBUG_EMAIL:
            logger.info("FROM: " + sender)
            logger.info("TO: " + address)
            logger.info("SUBJ: " + subject)
            logger.info("--------------")
            logger.info(message)
            logger.info("--------------")
            continue

        mail = EmailMultiAlternatives(
            subject, message, sender, [address], headers=headers
        )
        mail.send(fail_silently=kwargs.get("fail_silently", False))

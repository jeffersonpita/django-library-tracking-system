from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from .models import Loan


@shared_task
def send_loan_notification(loan_id):
    try:
        loan = Loan.objects.get(id=loan_id)
        member_email = loan.member.user.email
        book_title = loan.book.title
        send_mail(
            subject='Book Loaned Successfully',
            message=f'Hello {loan.member.user.username},\n\nYou have successfully loaned "{book_title}".\nPlease return it by the due date.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[member_email],
            fail_silently=False,
        )
    except Loan.DoesNotExist:
        pass

@shared_task
def check_overdue_loans():
    overdue_loans = Loan.objects.filter(is_returned=False, due_date__lt=timezone.now().date())
    for overdue_loan in overdue_loans:
        send_overdue_notification.delay(overdue_loan.id)


@shared_task
def send_overdue_notification(loan_id):
    try:
        loan = Loan.objects.select_related("member__user", "book").get(id=loan_id)
    except Loan.DoesNotExist:
        return

    send_mail(
        subject='Book Overdue Notice',
        message=(
            f'Hello {loan.member.user.username},\n\n'
            f'The book "{loan.book.title}" was due on {loan.due_date} and is now overdue.\n'
            f'Please return it as soon as possible.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[loan.member.user.email],
        fail_silently=False,
    )

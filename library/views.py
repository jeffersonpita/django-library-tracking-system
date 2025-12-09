from datetime import datetime, timedelta

from django.db.models import Count, Q
from django.forms.models import model_to_dict
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from library.pagination import CustomBookPagination

from .models import Author, Book, Loan, Member
from .serializers import AuthorSerializer, BookSerializer, LoanSerializer, MemberSerializer
from .tasks import send_loan_notification


class AuthorViewSet(viewsets.ModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer

class BookViewSet(viewsets.ModelViewSet):
    queryset = Book.objects.all().order_by('-id')
    serializer_class = BookSerializer
    pagination_class = CustomBookPagination

    def get_queryset(self):
        return Book.objects.select_related("author")


    @action(detail=True, methods=['post'])
    def loan(self, request, pk=None):
        book = self.get_object()
        if book.available_copies < 1:
            return Response({'error': 'No available copies.'}, status=status.HTTP_400_BAD_REQUEST)
        member_id = request.data.get('member_id')
        try:
            member = Member.objects.get(id=member_id)
        except Member.DoesNotExist:
            return Response({'error': 'Member does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan = Loan.objects.create(book=book, member=member)
        book.available_copies -= 1
        book.save()
        send_loan_notification.delay(loan.id)
        return Response({'status': 'Book loaned successfully.'}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def return_book(self, request, pk=None):
        book = self.get_object()
        member_id = request.data.get('member_id')
        try:
            loan = Loan.objects.get(book=book, member__id=member_id, is_returned=False)
        except Loan.DoesNotExist:
            return Response({'error': 'Active loan does not exist.'}, status=status.HTTP_400_BAD_REQUEST)
        loan.is_returned = True
        loan.return_date = timezone.now().date()
        loan.save()
        book.available_copies += 1
        book.save()
        return Response({'status': 'Book returned successfully.'}, status=status.HTTP_200_OK)

class MemberViewSet(viewsets.ModelViewSet):
    queryset = Member.objects.all()
    serializer_class = MemberSerializer

    @action(detail=False, url_path="top-active")
    def top_active(self, request):
        members = (
            Member.objects.annotate(active_loans=Count('loans', filter=Q(loans__is_returned=False)))
            .order_by('-active_loans', 'id')
        )
        page = self.paginate_queryset(members)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(members, many=True)
        return Response(serializer.data)




class LoanViewSet(viewsets.ModelViewSet):
    queryset = Loan.objects.all()
    serializer_class = LoanSerializer

    @action(detail=True, methods=['post'])
    def extend_due_date(self, request, pk=None):
        loan = self.get_object()
        if loan.due_date < timezone.now().date():
            return Response({'error': 'The loan is already overdue.'}, status=status.HTTP_400_BAD_REQUEST)
        additional_days = request.data.get('additional_days')
        if type(additional_days) != int or additional_days <= 0: 
            return Response({'error': 'Invalid parameters.'}, status=status.HTTP_400_BAD_REQUEST)
        
        loan.due_date += timedelta(additional_days)
        loan.save()
        return Response(model_to_dict(loan), status=status.HTTP_200_OK)

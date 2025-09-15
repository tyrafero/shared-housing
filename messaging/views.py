from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods, require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
import json

from .models import Conversation, Message, ConversationParticipant
from .services import MessagingService
from properties.models import Property

User = get_user_model()


@login_required
def conversations_list(request):
    """List user's conversations"""
    messaging_service = MessagingService()
    conversations = messaging_service.get_user_conversations(request.user)

    context = {
        'conversations': conversations,
        'unread_count': messaging_service.get_unread_count(request.user)
    }

    return render(request, 'messaging/conversations_list.html', context)


@login_required
def conversation_detail(request, conversation_id):
    """View conversation and messages"""
    conversation = get_object_or_404(
        Conversation.objects.prefetch_related('participants'),
        id=conversation_id
    )

    # Check if user is participant
    if not conversation.participants.filter(id=request.user.id).exists():
        raise Http404("Conversation not found")

    messaging_service = MessagingService()

    # Mark conversation as read
    messaging_service.mark_conversation_read(conversation, request.user)

    # Get messages (paginated)
    page = request.GET.get('page', 1)
    messages_list = messaging_service.get_conversation_messages(
        conversation,
        limit=50,
        offset=(int(page) - 1) * 50 if page != 1 else 0
    )

    # Get participant info
    participants = conversation.participants.select_related('profile').all()

    context = {
        'conversation': conversation,
        'messages': list(reversed(messages_list)),  # Show newest at bottom, convert to list
        'participants': participants,
        'websocket_url': f'ws/chat/{conversation_id}/',
        'current_user_id': request.user.id,
    }

    return render(request, 'messaging/conversation_detail.html', context)


@login_required
@require_POST
def send_message(request, conversation_id):
    """Send message via AJAX"""
    conversation = get_object_or_404(Conversation, id=conversation_id)

    # Check if user is participant
    if not conversation.participants.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Not authorized'}, status=403)

    # Handle both AJAX JSON and regular form POST
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            content = data.get('content', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        content = request.POST.get('content', '').strip()


    if not content:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'error': 'Message content cannot be empty'}, status=400)
        else:
            messages.error(request, 'Message content cannot be empty')
            return redirect('messaging:conversation_detail', conversation_id=conversation.id)

    # Send the message
    messaging_service = MessagingService()
    message = messaging_service.send_message(
        conversation=conversation,
        sender=request.user,
        content=content
    )

    # Return appropriate response based on request type
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # AJAX request - return JSON
        if message:
            return JsonResponse({
                'success': True,
                'message': {
                    'id': str(message.id),
                    'content': message.content,
                    'sender': {
                        'id': message.sender.id,
                        'name': message.sender.get_short_name()
                    },
                    'created_at': message.created_at.isoformat()
                }
            })
        else:
            return JsonResponse({'error': 'Failed to send message'}, status=500)
    else:
        # Regular form submission - redirect back to conversation
        # Messages are handled in the conversation interface
        return redirect('messaging:conversation_detail', conversation_id=conversation.id)


@login_required
def start_conversation(request):
    """Start a new conversation"""
    if request.method == 'POST':
        # Handle participant IDs from form
        participant_ids_str = request.POST.get('participant_ids', '')
        if participant_ids_str:
            participant_ids = [int(id.strip()) for id in participant_ids_str.split(',') if id.strip().isdigit()]
        else:
            participant_ids = request.POST.getlist('participants')

        conversation_type = request.POST.get('conversation_type', 'direct')
        title = request.POST.get('title', '')
        initial_message = request.POST.get('initial_message', '')
        property_id = request.POST.get('property_id')

        participants = User.objects.filter(
            id__in=participant_ids,
            is_active=True
        ).exclude(id=request.user.id)

        if not participants:
            return redirect('messaging:conversations_list')

        property_listing = None
        if property_id:
            property_listing = get_object_or_404(Property, id=property_id)

        messaging_service = MessagingService()
        conversation = messaging_service.start_conversation(
            initiator=request.user,
            participants=list(participants) + [request.user],
            conversation_type=conversation_type,
            title=title,
            property_listing=property_listing
        )

        # Send the initial message if provided
        if initial_message.strip():
            messaging_service.send_message(
                conversation=conversation,
                sender=request.user,
                content=initial_message.strip()
            )

        # Conversation started - redirect to conversation
        return redirect('messaging:conversation_detail', conversation_id=conversation.id)

    # GET request - show form
    preselected_user = None
    user_id = request.GET.get('user')

    if user_id:
        try:
            preselected_user = User.objects.get(
                id=user_id,
                is_active=True,
                profile_completed=True
            )
        except (User.DoesNotExist, ValueError):
            # User not found, continue with form
            pass

    # Get potential participants (users with complete profiles)
    potential_participants = User.objects.filter(
        profile_completed=True,
        is_active=True
    ).exclude(id=request.user.id).select_related('profile')[:20]

    context = {
        'potential_participants': potential_participants,
        'preselected_user': preselected_user,
    }

    return render(request, 'messaging/start_conversation.html', context)


@login_required
@require_POST
def property_inquiry(request, property_id):
    """Create inquiry conversation for a property"""
    property_listing = get_object_or_404(Property, id=property_id)
    message_content = request.POST.get('message', '')

    if not message_content.strip():
        return redirect('properties:detail', pk=property_id)

    try:
        messaging_service = MessagingService()
        conversation = messaging_service.create_property_inquiry(
            property_listing=property_listing,
            inquirer=request.user,
            message_content=message_content
        )

        return redirect('messaging:conversation_detail', conversation_id=conversation.id)

    except ValueError as e:
        return redirect('properties:detail', pk=property_id)


@login_required
def start_roommate_chat(request, user_id):
    """Start conversation with potential roommate"""
    other_user = get_object_or_404(User, id=user_id, is_active=True)

    if other_user == request.user:
        return redirect('core:dashboard')

    messaging_service = MessagingService()

    # Check if direct conversation already exists
    conversation, created = messaging_service.get_or_create_direct_conversation(
        request.user, other_user
    )

    if created:
        # Try to get compatibility score
        from roommate_matching.models import CompatibilityScore
        try:
            user1, user2 = (request.user, other_user) if request.user.id < other_user.id else (other_user, request.user)
            compatibility_score = CompatibilityScore.objects.get(user1=user1, user2=user2)

            # Send system message with compatibility info
            system_message = (
                f"You've connected with {other_user.get_short_name()}! "
                f"Compatibility score: {compatibility_score.overall_score:.0f}% "
                f"({compatibility_score.compatibility_level})"
            )
            messaging_service.send_system_message(conversation, system_message)

        except CompatibilityScore.DoesNotExist:
            # Send generic welcome message
            system_message = f"You've started a conversation with {other_user.get_short_name()}!"
            messaging_service.send_system_message(conversation, system_message)

    return redirect('messaging:conversation_detail', conversation_id=conversation.id)


@login_required
@require_http_methods(["GET"])
def messages_api(request, conversation_id):
    """API endpoint for getting messages"""
    conversation = get_object_or_404(Conversation, id=conversation_id)

    # Check if user is participant
    if not conversation.participants.filter(id=request.user.id).exists():
        return JsonResponse({'error': 'Not authorized'}, status=403)

    messaging_service = MessagingService()
    offset = int(request.GET.get('offset', 0))
    limit = int(request.GET.get('limit', 20))

    messages_list = messaging_service.get_conversation_messages(
        conversation,
        limit=limit,
        offset=offset
    )

    messages_data = []
    for message in messages_list:
        messages_data.append({
            'id': str(message.id),
            'content': message.content,
            'sender': {
                'id': message.sender.id if message.sender else None,
                'name': message.sender.get_short_name() if message.sender else 'System',
                'email': message.sender.email if message.sender else None
            },
            'message_type': message.message_type,
            'reply_to': str(message.reply_to.id) if message.reply_to else None,
            'created_at': message.created_at.isoformat(),
            'is_edited': message.is_edited,
            'has_attachment': message.has_attachment,
            'reactions': [
                {
                    'type': reaction.reaction_type,
                    'user': reaction.user.get_short_name(),
                    'emoji': dict(reaction.REACTION_TYPES)[reaction.reaction_type]
                }
                for reaction in message.reactions.select_related('user')
            ]
        })

    return JsonResponse({
        'messages': messages_data,
        'has_more': len(messages_list) == limit
    })


@login_required
@require_POST
def add_participants(request, conversation_id):
    """Add participants to conversation"""
    conversation = get_object_or_404(Conversation, id=conversation_id)

    # Check permissions
    try:
        participant = ConversationParticipant.objects.get(
            conversation=conversation,
            user=request.user
        )
        if not participant.can_add_participants and not participant.is_admin:
            return JsonResponse({'error': 'Permission denied'}, status=403)
    except ConversationParticipant.DoesNotExist:
        return JsonResponse({'error': 'Not authorized'}, status=403)

    try:
        data = json.loads(request.body)
        participant_ids = data.get('participant_ids', [])

        participants = User.objects.filter(
            id__in=participant_ids,
            is_active=True
        )

        messaging_service = MessagingService()
        success = messaging_service.add_participants(
            conversation=conversation,
            participants=list(participants),
            added_by=request.user
        )

        if success:
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'Failed to add participants'}, status=500)

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)


@login_required
@require_POST
def leave_conversation(request, conversation_id):
    """Leave a conversation"""
    conversation = get_object_or_404(Conversation, id=conversation_id)

    messaging_service = MessagingService()
    success = messaging_service.remove_participant(
        conversation=conversation,
        user_to_remove=request.user,
        removed_by=request.user
    )

    if success:
        return redirect('messaging:conversations_list')
    else:
        return redirect('messaging:conversation_detail', conversation_id=conversation_id)


@login_required
def search_messages(request):
    """Search messages"""
    query = request.GET.get('q', '').strip()
    conversation_id = request.GET.get('conversation_id')

    if not query:
        return JsonResponse({'messages': []})

    messaging_service = MessagingService()
    messages_list = messaging_service.search_messages(
        user=request.user,
        query=query,
        conversation_id=conversation_id
    )

    messages_data = []
    for message in messages_list:
        messages_data.append({
            'id': str(message.id),
            'content': message.content,
            'sender': {
                'name': message.sender.get_short_name() if message.sender else 'System'
            },
            'conversation': {
                'id': str(message.conversation.id),
                'title': str(message.conversation)
            },
            'created_at': message.created_at.isoformat()
        })

    return JsonResponse({'messages': messages_data})


@login_required
def user_search(request):
    """Search users for conversations"""
    query = request.GET.get('q', '').strip()

    if not query or len(query) < 2:
        return JsonResponse({'users': []})

    users = User.objects.filter(
        Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query),
        is_active=True,
        profile_completed=True
    ).exclude(id=request.user.id)[:10]

    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'name': user.get_short_name(),
            'email': user.email
        })

    return JsonResponse({'users': users_data})
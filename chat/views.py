from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, OuterRef, Subquery, Count, F
from django.db.models.functions import Coalesce
from django.db.utils import IntegrityError
from django.http import Http404
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET

from equipment.models import Equipment
from equipment.visit_tracking import is_bot_request
from equipment.finance_security import get_client_ip
from equipment.templatetags.i18n_extras import SUPPORTED_LANGS
from .models import ChatRoom, ChatMessage
from .security import (
    ban_user_chat,
    block_chat_ip,
    bump_chat_rate_limit,
    check_chat_rate_limit,
    is_user_chat_banned,
    validate_chat_message,
)


@require_GET
def set_language(request):
    """세션에 언어 저장 후 안전한 URL로 리다이렉트."""
    next_url = (request.GET.get('next') or '').strip()
    allowed_hosts = {request.get_host()}
    if is_bot_request(request):
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=allowed_hosts):
            return redirect(next_url)
        referer = request.META.get('HTTP_REFERER') or ''
        if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts=allowed_hosts):
            return redirect(referer)
        return redirect('/')

    lang = (request.GET.get('lang') or 'ko').strip().lower()
    if lang not in SUPPORTED_LANGS:
        lang = 'ko'
    request.session['lang'] = lang
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts=allowed_hosts):
        redirect_to = next_url
    else:
        referer = request.META.get('HTTP_REFERER') or ''
        if referer and url_has_allowed_host_and_scheme(referer, allowed_hosts=allowed_hosts):
            redirect_to = referer
        else:
            redirect_to = '/'
    return redirect(redirect_to)


@login_required(login_url='/login/')
def equipment_chat_start(request, pk):
    """매물 상세에서 '판매자에게 문의(채팅)' 클릭 시: 방 생성/조회 후 채팅방으로 리다이렉트."""
    if is_user_chat_banned(request.user):
        messages.error(request, '채팅 이용이 제한된 계정입니다.')
        return redirect('equipment_detail', pk=pk)
    equipment = get_object_or_404(Equipment, pk=pk)
    seller = equipment.author
    if not seller:
        return redirect('equipment_detail', pk=pk)
    buyer = request.user
    if buyer.id == seller.id:
        return redirect('equipment_detail', pk=pk)

    room = ChatRoom.objects.filter(
        equipment=equipment, buyer=buyer, seller=seller
    ).first()
    if room:
        return redirect('chat_room_detail', room_id=room.pk)

    # 동시 요청(더블탭/새로고침) 시 Unique 제약으로 한쪽이 IntegrityError → 기존 방 재조회 후 리다이렉트
    try:
        with transaction.atomic():
            room = ChatRoom.objects.create(
                equipment=equipment,
                buyer=buyer,
                seller=seller,
            )
    except IntegrityError:
        room = ChatRoom.objects.get(
            equipment=equipment, buyer=buyer, seller=seller
        )
    return redirect('chat_room_detail', room_id=room.pk)


@login_required(login_url='/login/')
def soil_chat_start(request, pk):
    """흙 게시글 상세에서 '채팅으로 문의하기' 클릭 시: 방 생성/조회 후 채팅방으로 리다이렉트."""
    if is_user_chat_banned(request.user):
        messages.error(request, '채팅 이용이 제한된 계정입니다.')
        return redirect('soil_detail', pk=pk)
    from soil.models import SoilPost
    post = get_object_or_404(SoilPost, pk=pk, is_active=True)
    seller = post.author
    buyer = request.user
    if buyer.id == seller.id:
        return redirect('soil_detail', pk=pk)

    room = ChatRoom.objects.filter(
        soil_post=post, buyer=buyer, seller=seller
    ).first()
    if room:
        return redirect('chat_room_detail', room_id=room.pk)

    try:
        with transaction.atomic():
            room = ChatRoom.objects.create(
                soil_post=post,
                buyer=buyer,
                seller=seller,
            )
    except IntegrityError:
        room = ChatRoom.objects.get(
            soil_post=post, buyer=buyer, seller=seller
        )
    return redirect('chat_room_detail', room_id=room.pk)


@login_required(login_url='/login/')
def job_chat_start(request, pk):
    """구인구직 상세에서 '문의하기' 클릭 시: 1:1 대화방 생성/조회 후 채팅방으로 리다이렉트."""
    if is_user_chat_banned(request.user):
        messages.error(request, '채팅 이용이 제한된 계정입니다.')
        return redirect('job_detail', pk=pk)
    from equipment.models import JobPost
    job = get_object_or_404(JobPost, pk=pk)
    seller = job.author
    if not seller:
        from django.contrib import messages
        messages.info(request, "문의는 로그인된 작성자 글에만 가능합니다.")
        return redirect('job_detail', pk=pk)
    buyer = request.user
    if buyer.id == seller.id:
        return redirect('job_detail', pk=pk)

    room = ChatRoom.objects.filter(
        job_post=job, buyer=buyer, seller=seller
    ).first()
    if room:
        return redirect('chat_room_detail', room_id=room.pk)

    try:
        with transaction.atomic():
            room = ChatRoom.objects.create(
                job_post=job,
                buyer=buyer,
                seller=seller,
            )
    except IntegrityError:
        room = ChatRoom.objects.get(
            job_post=job, buyer=buyer, seller=seller
        )
    return redirect('chat_room_detail', room_id=room.pk)


@login_required(login_url='/login/')
def chat_room_list(request):
    """내 채팅방 목록 (buyer 또는 seller로 참여 중인 방). Subquery로 최근 메시지 1개만 annotate해 N+1 방지."""
    if is_user_chat_banned(request.user):
        messages.error(request, '채팅 이용이 제한된 계정입니다.')
        return redirect('index')
    user = request.user
    last_msg_sub = ChatMessage.objects.filter(room=OuterRef('pk')).order_by('-created_at')
    rooms = (
        ChatRoom.objects.filter(Q(buyer=user) | Q(seller=user))
        .select_related('equipment', 'soil_post', 'job_post', 'buyer', 'seller')
        .annotate(
            last_msg_text=Subquery(last_msg_sub.values('message')[:1]),
            last_msg_created=Subquery(last_msg_sub.values('created_at')[:1]),
            unread_count=Count('messages', filter=Q(messages__is_read=False) & ~Q(messages__sender=user)),
        )
        .order_by(Coalesce(F('last_message_at'), F('updated_at')).desc())
    )
    room_list_data = []
    for room in rooms:
        other = room.seller if room.buyer_id == user.id else room.buyer
        # 현재 사용자 기준: 내가 구매자면 상대는 판매자, 내가 판매자면 상대는 구매자
        other_role = 'seller' if room.buyer_id == user.id else 'buyer'
        last_text = room.last_msg_text or ''
        if len(last_text) > 50:
            last_text = last_text[:50] + '...'
        if room.equipment_id:
            mn = getattr(room.equipment, 'model_name', None) or room.equipment.get_equipment_type_display()
            subject = f"{mn} · {room.equipment.listing_price:,.0f}만원"
        elif room.soil_post_id:
            subject = room.soil_post.title
        elif room.job_post_id:
            subject = room.job_post.title
        else:
            subject = ''
        room_list_data.append({
            'room': room,
            'other': other,
            'other_role': other_role,
            'subject': subject,
            'last_message': last_text,
            'last_at': room.last_msg_created or room.updated_at,
            'unread_count': room.unread_count or 0,
        })
    return render(request, 'chat/room_list.html', {'room_list_data': room_list_data})


@login_required(login_url='/login/')
def chat_room_detail(request, room_id):
    """채팅방 상세: 메시지 목록 + 전송. 해당 방의 buyer/seller만 접근 가능. 권한 없으면 404(URL guessing 방지)."""
    if is_user_chat_banned(request.user):
        messages.error(request, '채팅 이용이 제한된 계정입니다.')
        return redirect('chat_room_list')

    room = get_object_or_404(ChatRoom.objects.select_related('equipment', 'soil_post', 'job_post'), pk=room_id)
    user = request.user
    if room.buyer_id != user.id and room.seller_id != user.id:
        raise Http404()
    other = room.seller if room.buyer_id == user.id else room.buyer

    # 상대가 보낸 메시지만 읽음 처리(내가 보낸 건 제외). 목록 미읽음 Count 0으로 감
    room.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)

    if request.method == 'POST':
        rate_msg = check_chat_rate_limit(request)
        if rate_msg:
            messages.error(request, rate_msg)
            return redirect('chat_room_detail', room_id=room_id)

        raw_text = request.POST.get('message') or ''
        try:
            msg_text = validate_chat_message(raw_text)
        except ValidationError as exc:
            messages.error(request, exc.messages[0] if exc.messages else '메시지를 확인해 주세요.')
            block_chat_ip(get_client_ip(request), seconds=3600)
            if is_user_chat_banned(user) is False:
                recent_attack_key = f'chat_attack:u{user.id}'
                attack_count = cache.get(recent_attack_key, 0) + 1
                cache.set(recent_attack_key, attack_count, 3600)
                if attack_count >= 3:
                    ban_user_chat(user)
                    messages.error(request, '비정상 메시지가 반복되어 계정이 차단되었습니다.')
                    return redirect('chat_room_list')
            return redirect('chat_room_detail', room_id=room_id)

        ChatMessage.objects.create(room=room, sender=user, message=msg_text)
        bump_chat_rate_limit(request)
        room.last_message_at = timezone.now()
        room.save(update_fields=['last_message_at', 'updated_at'])
        return redirect('chat_room_detail', room_id=room_id)

    chat_messages = room.messages.select_related('sender').order_by('created_at')
    return render(request, 'chat/room_detail.html', {
        'room': room,
        'other': other,
        'chat_messages': chat_messages,
    })

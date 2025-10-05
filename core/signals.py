from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import Profile, Notification, Post, Comment, Like
import os


@receiver(pre_save, sender=Profile)
def delete_old_avatar(sender, instance, **kwargs):
    # if creating a new profile, do nothing
    if not instance.pk:
        return

    try:
        old_profile = Profile.objects.get(pk=instance.pk)
        # if avatar is updated and the old one is not the default
        if old_profile.avatar and old_profile.avatar.url != instance.avatar.url and 'default.png' not in old_profile.avatar.url:
            if os.path.isfile(old_profile.avatar.path):
                os.remove(old_profile.avatar.path)
    except Profile.DoesNotExist:
        # This can happen if the profile is being created, but the check for instance.pk should prevent it.
        # It's good practice to have it anyway.
        pass


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    # Do not create a profile if loading data from a fixture
    if kwargs.get('raw', False):
        return
    if created:
        Profile.objects.create(user=instance)
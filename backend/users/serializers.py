from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from .models import User, CandidateProfile, RecruiterProfile

class CandidateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = CandidateProfile
        fields = ['resume', 'skills', 'bio', 'phone']

class RecruiterProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecruiterProfile
        fields = ['company_name', 'company_description', 'website', 'phone']

class UserSerializer(serializers.ModelSerializer):
    candidate_profile = CandidateProfileSerializer(read_only=True)
    recruiter_profile = RecruiterProfileSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'is_candidate', 'is_recruiter', 'candidate_profile', 'recruiter_profile']
        read_only_fields = ['id', 'is_candidate', 'is_recruiter']

class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['candidate', 'recruiter'])

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'role']

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if settings.PILOT_INVITE_ONLY:
            email = (attrs.get('email') or '').strip()
            if email.casefold() not in settings.PILOT_INVITED_EMAILS:
                raise serializers.ValidationError({
                    'email': 'Registration is limited to invited pilot participants.'
                })
            attrs['email'] = email
        return attrs

    def create(self, validated_data):
        role = validated_data.pop('role')
        user = User.objects.create_user(**validated_data)
        if role == 'candidate':
            user.is_candidate = True
            CandidateProfile.objects.create(user=user)
        else:
            user.is_recruiter = True
            RecruiterProfile.objects.create(user=user)
        user.save()
        return user

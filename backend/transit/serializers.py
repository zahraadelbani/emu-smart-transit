from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from . import models


class ValidatedModelSerializer(serializers.ModelSerializer):
    def validate(self, attrs):
        instance = self.instance or self.Meta.model()
        for key, value in attrs.items():
            field = instance._meta.get_field(key)
            if not field.many_to_many:
                setattr(instance, key, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else exc.messages)
        return attrs


class LineSerializer(ValidatedModelSerializer):
    class Meta:
        model = models.Line
        fields = '__all__'


class StopSerializer(ValidatedModelSerializer):
    class Meta:
        model = models.Stop
        fields = '__all__'


class RouteStopSerializer(ValidatedModelSerializer):
    stop_detail = StopSerializer(source='stop', read_only=True)

    class Meta:
        model = models.RouteStop
        fields = '__all__'


class RouteSerializer(ValidatedModelSerializer):
    lines = LineSerializer(many=True, read_only=True)
    line_ids = serializers.PrimaryKeyRelatedField(queryset=models.Line.objects.all(), many=True, write_only=True, required=False)
    ordered_stops = RouteStopSerializer(many=True, read_only=True)

    class Meta:
        model = models.Route
        fields = '__all__'

    def validate(self, attrs):
        line_ids = attrs.pop('line_ids', None)
        attrs = super().validate(attrs)
        if self.instance is None and not line_ids:
            raise serializers.ValidationError({'line_ids': 'Select at least one service line'})
        if line_ids is None and self.instance is not None and 'combined' in attrs:
            if attrs['combined'] != (self.instance.lines.count() > 1):
                raise serializers.ValidationError('Combined classification must match service line count')
        if line_ids is not None:
            if len(set(l.pk for l in line_ids)) != len(line_ids):
                raise serializers.ValidationError('Duplicate service lines')
            combined = attrs.get('combined', getattr(self.instance, 'combined', False))
            if combined != (len(line_ids) > 1):
                raise serializers.ValidationError('Combined classification must match service line count')
            attrs['line_ids'] = line_ids
        return attrs

    def create(self, validated_data):
        lines = validated_data.pop('line_ids', [])
        route = super().create(validated_data)
        route.lines.set(lines)
        return route

    def update(self, instance, validated_data):
        lines = validated_data.pop('line_ids', None)
        route = super().update(instance, validated_data)
        if lines is not None:
            route.lines.set(lines)
        return route


def model_serializer(model):
    meta = type('Meta', (), {'model': model, 'fields': '__all__'})
    return type(model.__name__ + 'Serializer', (ValidatedModelSerializer,), {'Meta': meta})


ScheduleSerializer = model_serializer(models.Schedule)
AnnouncementSerializer = model_serializer(models.Announcement)

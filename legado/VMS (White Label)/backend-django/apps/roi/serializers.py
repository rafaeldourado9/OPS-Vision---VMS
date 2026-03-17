from rest_framework import serializers
from .models import RegionOfInterest


class RegionOfInterestSerializer(serializers.ModelSerializer):
    # Frontend usa polygon_points e enabled; backend usa polygon e active
    polygon_points = serializers.JSONField(source='polygon', required=False)
    enabled = serializers.BooleanField(source='active', required=False)

    class Meta:
        model = RegionOfInterest
        fields = [
            'id', 'camera', 'name',
            'polygon_points', 'enabled',   # aliases frontend
            'polygon', 'active',           # campos reais do modelo
            'ia_type', 'ia_types', 'config', 'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'polygon', 'active']

    def to_representation(self, instance):
        rep = super().to_representation(instance)
        # Garante que polygon_points e enabled estão presentes na leitura
        rep['polygon_points'] = instance.polygon
        rep['enabled'] = instance.active
        return rep

    def validate_polygon_points(self, value):
        # Multi-analytic mode (ia_types) or explicit line_crossing → 2 points min
        is_line = (
            bool(self.initial_data.get('ia_types'))
            or self.initial_data.get('ia_type') == 'line_crossing'
        )
        min_points = 2 if is_line else 3
        if not isinstance(value, list) or len(value) < min_points:
            raise serializers.ValidationError(
                f'{"Linha precisa de 2" if is_line else "Polígono precisa de 3"} pontos mínimo'
            )
        for point in value:
            if not isinstance(point, list) or len(point) != 2:
                raise serializers.ValidationError('Cada ponto deve ser [x, y]')
            x, y = point
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise serializers.ValidationError('Coordenadas devem estar entre 0 e 1')
        return value

from rest_framework import serializers
from .models import RegionOfInterest


class RegionOfInterestSerializer(serializers.ModelSerializer):
    class Meta:
        model = RegionOfInterest
        fields = ['id', 'camera', 'name', 'polygon', 'ia_type', 'active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_polygon(self, value):
        """Valida que polígono tem pelo menos 3 pontos"""
        if not isinstance(value, list) or len(value) < 3:
            raise serializers.ValidationError('Polígono deve ter pelo menos 3 pontos')
        
        for point in value:
            if not isinstance(point, list) or len(point) != 2:
                raise serializers.ValidationError('Cada ponto deve ter formato [x, y]')
            
            x, y = point
            if not (0 <= x <= 1 and 0 <= y <= 1):
                raise serializers.ValidationError('Coordenadas devem estar entre 0 e 1')
        
        return value

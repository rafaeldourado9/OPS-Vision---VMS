Feature: Operator queries system events
  As an operator or frontend system
  I want to query system events with various filters
  So that I can monitor ALPR detections, camera statuses, and audit logs.

  Background:
    Given an authenticated user "operator1" for tenant "tenant-x"
    And the tenant "tenant-x" has a camera "Cam Frontal"
    And an ALPR event exists for "Cam Frontal" with plate "ABC1234" and confidence 0.95
    And an ALPR event exists for "Cam Frontal" with plate "XYZ9876" and confidence 0.80
    And the tenant "tenant-y" has a camera "Cam Fundos"
    And an ALPR event exists for "Cam Fundos" with plate "FGH4567" and confidence 0.99

  Scenario: Tenant isolation prevents cross-tenant queries
    When the user requests the list of events
    Then the response should contain 2 events
    And all returned events should belong to "tenant-x"
    And the plate "FGH4567" should not be in the response

  Scenario: Operator filters ALPR detections by high confidence and plate partial match
    When the user filters events with "confidence_gte" set to "0.90" and "plate__icontains" set to "abc"
    Then the response should contain 1 event
    And the returned event should have plate "ABC1234"

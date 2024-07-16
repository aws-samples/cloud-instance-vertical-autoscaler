import unittest
from unittest.mock import MagicMock, patch
import ec2_vertical_scale_check

class TestEc2VerticalScaleCheck(unittest.TestCase):

    @patch('ec2_vertical_scale_check.ec2_client')
    def test_calculate_desired_instance_type(self, mock_ec2_client):
        # Test case 1: Memory utilization below the scaling-down threshold
        mem_utilization = 30
        current_instance_type = 't2.medium'
        expected_instance_type = 't2.small'
        result = ec2_vertical_scale_check.calculate_desired_instance_type(mem_utilization, current_instance_type)
        self.assertEqual(result, expected_instance_type)

        # Test case 2: Memory utilization within the normal range
        mem_utilization = 60
        current_instance_type = 't2.large'
        expected_instance_type = 't2.large'
        result = ec2_vertical_scale_check.calculate_desired_instance_type(mem_utilization, current_instance_type)
        self.assertEqual(result, expected_instance_type)

        # Test case 3: Memory utilization above the scaling-up threshold
        mem_utilization = 95
        current_instance_type = 't2.small'
        expected_instance_type = 't2.medium'
        result = ec2_vertical_scale_check.calculate_desired_instance_type(mem_utilization, current_instance_type)
        self.assertEqual(result, expected_instance_type)

    @patch('ec2_vertical_scale_check.ec2_client')
    def test_scale_ec2_instance(self, mock_ec2_client):
        # Test case 1: Successful scaling operation
        instance_id = 'i-0123456789abcdef'
        desired_instance_type = 't2.small'
        mock_ec2_client.modify_instance_attribute.return_value = None
        result = ec2_vertical_scale_check.scale_ec2_instance(instance_id, desired_instance_type)
        self.assertEqual(result, f"Successfully scaled instance {instance_id} to {desired_instance_type}")

        # Test case 2: Failed scaling operation (e.g., insufficient permissions)
        instance_id = 'i-0123456789abcdef'
        desired_instance_type = 't2.small'
        mock_ec2_client.modify_instance_attribute.side_effect = Exception("Access Denied")
        result = ec2_vertical_scale_check.scale_ec2_instance(instance_id, desired_instance_type)
        self.assertEqual(result, f"Failed to scale instance {instance_id}: Access Denied")

if __name__ == '__main__':
    unittest.main()

CREATE TRIGGER sandbox_trigger BEFORE INSERT ON tabSandbox
FOR EACH ROW
SET NEW.test_data = 'test';



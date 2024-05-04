def validateEnv(env, requiredFields):
    for required in requiredFields:
        if required not in env:
            print("Variable {0} is not specified in your dotenv (.env) file!".format(required))
            return False 
        
    # Check if ports are in valid range
    if 'PROTOCOL_PORT' in env and (not 1 <= int(env['PROTOCOL_PORT']) <= 65535):
        print("PROTOCOL_PORT is defined as {0}. Needs to be between 1-65535.".format(env['PROTOCOL_PORT']))
        return False
    
    if 'REGISTRY_PROTOCOL_PORT' in env and (not 1 <= int(env['REGISTRY_PROTOCOL_PORT']) <= 65535):
        print("REGISTRY_PROTOCOL_PORT is defined as {0}. Needs to be between 1-65535.".format(env['REGISTRY_PROTOCOL_PORT']))
    return True
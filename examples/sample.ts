/**
 * Example TypeScript file for testing the AST parser
 */
import { EventEmitter } from 'events';

/**
 * Interface for a user object
 */
interface User {
  id: number;
  name: string;
  email: string;
  isActive?: boolean;
}

/**
 * Base class for entities
 */
abstract class BaseEntity {
  protected id: number;
  
  /**
   * Creates a new entity
   * @param id The entity ID
   */
  constructor(id: number) {
    this.id = id;
  }
  
  /**
   * Get the entity ID
   * @returns The entity ID
   */
  public getId(): number {
    return this.id;
  }
  
  /**
   * Abstract method to validate the entity
   */
  abstract validate(): boolean;
}

/**
 * Represents a user in the system
 */
class UserEntity extends BaseEntity implements User {
  public name: string;
  public email: string;
  private isActive: boolean = true;
  
  /**
   * Creates a new user
   * @param id User ID
   * @param name User name
   * @param email User email
   */
  constructor(id: number, name: string, email: string) {
    super(id);
    this.name = name;
    this.email = email;
  }
  
  /**
   * Validates the user entity
   * @returns True if valid, false otherwise
   */
  public validate(): boolean {
    return (
      this.id > 0 &&
      this.name.trim().length > 0 &&
      /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.email)
    );
  }
  
  /**
   * Deactivate the user
   */
  public deactivate(): void {
    this.isActive = false;
  }
}

/**
 * User service for managing users
 */
class UserService {
  private users: Map<number, UserEntity> = new Map();
  private events: EventEmitter = new EventEmitter();
  
  /**
   * Add a user to the service
   * @param user The user to add
   */
  public addUser(user: UserEntity): void {
    if (!user.validate()) {
      throw new Error('Invalid user');
    }
    
    this.users.set(user.getId(), user);
    this.events.emit('user:added', user);
  }
  
  /**
   * Get a user by ID
   * @param id The user ID
   * @returns The user, or undefined if not found
   */
  public getUser(id: number): UserEntity | undefined {
    return this.users.get(id);
  }
  
  /**
   * Get all users
   * @returns Array of all users
   */
  public getAllUsers(): UserEntity[] {
    return Array.from(this.users.values());
  }
}

// Create and use a user service
const userService = new UserService();
const user1 = new UserEntity(1, 'John Doe', 'john@example.com');
const user2 = new UserEntity(2, 'Jane Smith', 'jane@example.com');

userService.addUser(user1);
userService.addUser(user2);

console.log('All users:', userService.getAllUsers()); 